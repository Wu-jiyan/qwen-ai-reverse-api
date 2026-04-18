"""节点健康检测模块 - 自动测试节点可用性

支持并发测试、延迟测量和结果标记
"""

import asyncio
import time
import logging
from typing import List, Dict, Optional, Callable, Any, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

import aiohttp

from .subscription import VlessNode, SubscriptionManager, get_subscription_manager
from .node_storage import NodeStorage, get_node_storage
from .vless_proxy import VlessProxy

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """测试结果"""
    identifier: str
    success: bool
    latency: float  # 毫秒
    error: Optional[str] = None
    timestamp: float = 0
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


class NodeTester:
    """节点测试器"""
    
    # 测试目标
    TEST_TARGETS = [
        ('https://www.google.com', 'Google'),
        ('https://www.cloudflare.com', 'Cloudflare'),
        ('https://chat.qwen.ai', 'Qwen AI'),
    ]
    
    def __init__(self, 
                 max_concurrent: int = 10,
                 test_timeout: int = 10,
                 retry_times: int = 2):
        """
        初始化测试器
        
        Args:
            max_concurrent: 最大并发测试数
            test_timeout: 测试超时时间（秒）
            retry_times: 失败重试次数
        """
        self.max_concurrent = max_concurrent
        self.test_timeout = test_timeout
        self.retry_times = retry_times
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._storage: Optional[NodeStorage] = None
        self._subscription_manager: Optional[SubscriptionManager] = None
    
    async def init(self):
        """初始化存储和订阅管理器"""
        self._storage = get_node_storage()
        await self._storage.load()
        self._subscription_manager = get_subscription_manager()
    
    async def test_node(self, node: VlessNode, target_url: Optional[str] = None) -> TestResult:
        """
        测试单个节点
        
        Args:
            node: 要测试的节点
            target_url: 测试目标URL，默认使用Google
            
        Returns:
            测试结果
        """
        async with self._semaphore:
            target = target_url or self.TEST_TARGETS[0][0]
            
            for attempt in range(self.retry_times):
                try:
                    start_time = time.time()
                    
                    # 创建Vless代理连接
                    proxy = VlessProxy(node.uri)
                    
                    # 测试连接
                    success = await proxy.test_connection(
                        target_host=self._extract_host(target),
                        target_port=443 if target.startswith('https') else 80,
                        timeout=self.test_timeout
                    )
                    
                    latency = (time.time() - start_time) * 1000  # 转换为毫秒
                    
                    if success:
                        return TestResult(
                            identifier=node.identifier,
                            success=True,
                            latency=latency
                        )
                    
                    # 如果失败且还有重试机会
                    if attempt < self.retry_times - 1:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    error_msg = str(e)
                    if attempt < self.retry_times - 1:
                        await asyncio.sleep(1)
                    else:
                        return TestResult(
                            identifier=node.identifier,
                            success=False,
                            latency=0,
                            error=error_msg
                        )
            
            return TestResult(
                identifier=node.identifier,
                success=False,
                latency=0,
                error="All retry attempts failed"
            )
    
    async def test_nodes(self, nodes: List[VlessNode], 
                        progress_callback: Optional[Callable[[int, int], None]] = None) -> List[TestResult]:
        """
        批量测试节点
        
        Args:
            nodes: 节点列表
            progress_callback: 进度回调函数 (current, total)
            
        Returns:
            测试结果列表
        """
        results = []
        total = len(nodes)
        
        async def test_with_progress(node: VlessNode, index: int) -> TestResult:
            result = await self.test_node(node)
            if progress_callback:
                progress_callback(index + 1, total)
            return result
        
        # 创建任务
        tasks = [
            test_with_progress(node, i)
            for i, node in enumerate(nodes)
        ]
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(TestResult(
                    identifier=nodes[i].identifier,
                    success=False,
                    latency=0,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def test_all_available_nodes(self, 
                                       pattern: Optional[str] = None,
                                       progress_callback: Optional[Callable[[int, int], None]] = None) -> List[TestResult]:
        """
        测试所有可用节点
        
        Args:
            pattern: 节点名称匹配规则
            progress_callback: 进度回调
            
        Returns:
            测试结果列表
        """
        if self._storage is None:
            await self.init()
        
        # 获取要测试的节点
        if pattern:
            nodes = self._storage.get_nodes_by_pattern(pattern)
        else:
            nodes = self._storage.get_available_nodes()
        
        if not nodes:
            logger.warning("No nodes to test")
            return []
        
        logger.info(f"Testing {len(nodes)} nodes" + (f" with pattern '{pattern}'" if pattern else ""))
        
        results = await self.test_nodes(nodes, progress_callback)
        
        # 更新存储
        await self._update_storage_with_results(results)
        
        return results
    
    async def test_and_update_subscriptions(self, 
                                            patterns: Optional[List[str]] = None,
                                            progress_callback: Optional[Callable[[int, int], None]] = None) -> Dict[str, List[TestResult]]:
        """
        获取最新订阅并测试
        
        Args:
            patterns: 要测试的节点规则列表
            progress_callback: 进度回调
            
        Returns:
            各规则的测试结果
        """
        if self._subscription_manager is None:
            self._subscription_manager = get_subscription_manager()
        
        if self._storage is None:
            self._storage = get_node_storage()
            await self._storage.load()
        
        # 1. 获取最新订阅
        logger.info("Fetching subscriptions...")
        await self._subscription_manager.fetch_all()
        
        # 2. 合并到存储
        all_sub_nodes = []
        for sub in self._subscription_manager.subscriptions.values():
            all_sub_nodes.extend(sub.nodes)
        
        await self._storage.merge_with_subscription(all_sub_nodes)
        
        # 3. 测试节点
        results_by_pattern = {}
        
        patterns_to_test = patterns or list(self._subscription_manager.available_nodes.keys())
        
        for pattern in patterns_to_test:
            nodes = self._subscription_manager.get_nodes_by_pattern(pattern, only_available=False)
            if not nodes:
                continue
            
            logger.info(f"Testing {len(nodes)} nodes for pattern '{pattern}'")
            results = await self.test_nodes(nodes, progress_callback)
            results_by_pattern[pattern] = results
            
            # 更新存储
            await self._update_storage_with_results(results)
        
        return results_by_pattern
    
    async def _update_storage_with_results(self, results: List[TestResult]):
        """根据测试结果更新存储"""
        if self._storage is None:
            return
        
        for result in results:
            await self._storage.mark_node_result(
                identifier=result.identifier,
                success=result.success,
                latency=result.latency,
                auto_save=False  # 批量保存
            )
        
        # 批量保存
        await self._storage.save()
    
    def _extract_host(self, url: str) -> str:
        """从URL提取主机名"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.hostname or 'www.google.com'
    
    async def get_recommended_nodes(self, pattern: str, 
                                    min_success_rate: float = 0.8,
                                    max_latency: float = 1000,
                                    limit: int = 5) -> List[VlessNode]:
        """
        获取推荐节点（高质量节点）
        
        Args:
            pattern: 节点规则
            min_success_rate: 最小成功率
            max_latency: 最大延迟（毫秒）
            limit: 返回数量
            
        Returns:
            推荐节点列表
        """
        if self._storage is None:
            await self.init()
        
        nodes = self._storage.get_nodes_by_pattern(pattern)
        
        # 筛选高质量节点
        qualified = []
        for node in nodes:
            if not node.is_available:
                continue
            
            total = node.success_count + node.fail_count
            if total == 0:
                # 未测试过的节点也加入候选
                qualified.append((node, 0, float('inf')))
                continue
            
            success_rate = node.success_count / total
            if success_rate >= min_success_rate and node.average_latency <= max_latency:
                qualified.append((node, success_rate, node.average_latency))
        
        # 排序：成功率高优先，其次延迟低
        qualified.sort(key=lambda x: (-x[1], x[2]))
        
        return [node for node, _, _ in qualified[:limit]]
    
    async def get_random_qualified_node(self, pattern: str) -> Optional[VlessNode]:
        """随机获取一个合格的节点"""
        import random
        
        nodes = await self.get_recommended_nodes(pattern, limit=10)
        if not nodes:
            # 如果没有合格节点，尝试获取任何可用节点
            if self._storage is None:
                await self.init()
            nodes = self._storage.get_nodes_by_pattern(pattern)
            nodes = [n for n in nodes if n.is_available]
        
        if not nodes:
            return None
        
        return random.choice(nodes)
    
    def get_test_summary(self, results: List[TestResult]) -> Dict[str, Any]:
        """获取测试摘要"""
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success
        
        latencies = [r.latency for r in results if r.success and r.latency > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'success_rate': success / total if total > 0 else 0,
            'latency': {
                'avg': round(avg_latency, 2),
                'min': round(min_latency, 2),
                'max': round(max_latency, 2)
            }
        }


# 全局测试器实例
_global_tester: Optional[NodeTester] = None


def get_node_tester(max_concurrent: int = 10) -> NodeTester:
    """获取全局测试器"""
    global _global_tester
    if _global_tester is None:
        _global_tester = NodeTester(max_concurrent=max_concurrent)
    return _global_tester


async def init_node_tester(max_concurrent: int = 10) -> NodeTester:
    """初始化节点测试器"""
    tester = get_node_tester(max_concurrent)
    await tester.init()
    return tester
