"""订阅管理模块 - 从订阅URL获取和解析Vless节点

支持从订阅URL获取节点，按规则筛选，并进行本地存储
"""

import base64
import json
import re
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Callable, Any, Set
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse, unquote
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class VlessNode:
    """Vless节点数据类"""
    uri: str                          # 原始URI
    name: str                         # 节点名称/别名
    address: str                      # 服务器地址
    port: int                         # 端口
    uuid: str                         # UUID
    network: str = "tcp"              # 传输类型
    security: str = "none"          # 安全类型
    host: Optional[str] = None        # 主机名
    path: Optional[str] = None        # 路径
    sni: Optional[str] = None         # SNI
    tls: bool = False                 # 是否TLS
    # 元数据
    source_subscription: str = ""     # 来源订阅URL
    remarks_pattern: str = ""         # 匹配的规则
    added_time: str = field(default_factory=lambda: datetime.now().isoformat())
    last_tested: Optional[str] = None # 最后测试时间
    is_available: bool = True         # 是否可用
    fail_count: int = 0               # 失败次数
    success_count: int = 0            # 成功次数
    average_latency: float = 0.0      # 平均延迟
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VlessNode':
        """从字典创建"""
        return cls(**data)
    
    @property
    def identifier(self) -> str:
        """节点唯一标识"""
        return f"{self.address}:{self.port}"
    
    def mark_success(self, latency: float):
        """标记成功"""
        self.success_count += 1
        self.fail_count = 0
        self.is_available = True
        self.last_tested = datetime.now().isoformat()
        # 更新平均延迟
        if self.average_latency == 0:
            self.average_latency = latency
        else:
            self.average_latency = (self.average_latency * (self.success_count - 1) + latency) / self.success_count
    
    def mark_fail(self):
        """标记失败"""
        self.fail_count += 1
        self.last_tested = datetime.now().isoformat()
        if self.fail_count >= 3:
            self.is_available = False


class SubscriptionManager:
    """订阅管理器"""
    
    def __init__(self):
        self.subscriptions: Dict[str, 'Subscription'] = {}
        self.all_nodes: Dict[str, VlessNode] = {}  # identifier -> node
        self.available_nodes: Dict[str, List[VlessNode]] = {}  # pattern -> nodes
        self._lock = asyncio.Lock()
    
    def add_subscription(self, url: str, name: str = "", 
                        remarks_patterns: Optional[List[str]] = None,
                        auto_update_interval: int = 3600) -> 'Subscription':
        """
        添加订阅
        
        Args:
            url: 订阅URL
            name: 订阅名称
            remarks_patterns: 节点名称匹配规则列表，如 ["CF优选-电信", "CF优选-移动"]
            auto_update_interval: 自动更新间隔（秒）
        """
        sub = Subscription(
            url=url,
            name=name,
            remarks_patterns=remarks_patterns or [],
            auto_update_interval=auto_update_interval,
            manager=self
        )
        self.subscriptions[url] = sub
        return sub
    
    async def fetch_all(self) -> Dict[str, List[VlessNode]]:
        """获取所有订阅的节点"""
        results = {}
        for url, sub in self.subscriptions.items():
            try:
                nodes = await sub.fetch()
                results[url] = nodes
                # 更新节点存储
                await self._update_nodes(nodes, sub.remarks_patterns)
            except Exception as e:
                logger.error(f"Failed to fetch subscription {url}: {e}")
                results[url] = []
        return results
    
    async def _update_nodes(self, nodes: List[VlessNode], patterns: List[str]):
        """更新节点存储"""
        async with self._lock:
            for node in nodes:
                # 检查是否已存在
                if node.identifier in self.all_nodes:
                    # 保留状态信息
                    existing = self.all_nodes[node.identifier]
                    node.is_available = existing.is_available
                    node.fail_count = existing.fail_count
                    node.success_count = existing.success_count
                    node.average_latency = existing.average_latency
                
                self.all_nodes[node.identifier] = node
                
                # 按规则分类
                for pattern in patterns:
                    if pattern in node.name or re.search(pattern, node.name):
                        if pattern not in self.available_nodes:
                            self.available_nodes[pattern] = []
                        # 避免重复
                        if not any(n.identifier == node.identifier for n in self.available_nodes[pattern]):
                            self.available_nodes[pattern].append(node)
                        node.remarks_pattern = pattern
    
    def get_nodes_by_pattern(self, pattern: str, only_available: bool = True) -> List[VlessNode]:
        """
        按规则获取节点
        
        Args:
            pattern: 匹配规则
            only_available: 是否只返回可用节点
        """
        nodes = self.available_nodes.get(pattern, [])
        if only_available:
            return [n for n in nodes if n.is_available]
        return nodes
    
    def get_random_node(self, pattern: str) -> Optional[VlessNode]:
        """随机获取一个节点"""
        import random
        nodes = self.get_nodes_by_pattern(pattern, only_available=True)
        if not nodes:
            return None
        return random.choice(nodes)
    
    def get_all_available_nodes(self) -> List[VlessNode]:
        """获取所有可用节点"""
        return [n for n in self.all_nodes.values() if n.is_available]
    
    def mark_node_result(self, identifier: str, success: bool, latency: float = 0):
        """标记节点使用结果"""
        if identifier in self.all_nodes:
            node = self.all_nodes[identifier]
            if success:
                node.mark_success(latency)
            else:
                node.mark_fail()
            # 同步更新分类列表中的节点
            for pattern, nodes in self.available_nodes.items():
                for n in nodes:
                    if n.identifier == identifier:
                        if success:
                            n.mark_success(latency)
                        else:
                            n.mark_fail()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.all_nodes)
        available = len(self.get_all_available_nodes())
        
        pattern_stats = {}
        for pattern, nodes in self.available_nodes.items():
            available_count = len([n for n in nodes if n.is_available])
            pattern_stats[pattern] = {
                'total': len(nodes),
                'available': available_count,
                'unavailable': len(nodes) - available_count
            }
        
        return {
            'total_nodes': total,
            'available_nodes': available,
            'unavailable_nodes': total - available,
            'subscriptions': len(self.subscriptions),
            'patterns': pattern_stats
        }


class Subscription:
    """单个订阅"""
    
    def __init__(self, url: str, name: str = "", 
                 remarks_patterns: Optional[List[str]] = None,
                 auto_update_interval: int = 3600,
                 manager: Optional[SubscriptionManager] = None):
        self.url = url
        self.name = name or url
        self.remarks_patterns = remarks_patterns or []
        self.auto_update_interval = auto_update_interval
        self.manager = manager
        self.last_update: Optional[datetime] = None
        self.nodes: List[VlessNode] = []
        
    async def fetch(self, force: bool = False) -> List[VlessNode]:
        """
        获取订阅内容
        
        Args:
            force: 是否强制刷新
        """
        # 检查是否需要更新
        if not force and self.last_update:
            elapsed = (datetime.now() - self.last_update).total_seconds()
            if elapsed < self.auto_update_interval:
                return self.nodes
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        raise ValueError(f"HTTP {response.status}")
                    
                    content = await response.text()
                    self.nodes = self._parse_content(content)
                    self.last_update = datetime.now()
                    
                    logger.info(f"Fetched {len(self.nodes)} nodes from {self.name}")
                    return self.nodes
                    
        except Exception as e:
            logger.error(f"Failed to fetch subscription {self.name}: {e}")
            raise
    
    def _parse_content(self, content: str) -> List[VlessNode]:
        """解析订阅内容"""
        nodes = []
        
        # 尝试Base64解码
        decoded = self._try_base64_decode(content)
        if decoded:
            lines = decoded.strip().split('\n')
        else:
            lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 解析Vless URI
            if line.startswith('vless://'):
                try:
                    node = self._parse_vless_uri(line)
                    if node:
                        # 检查是否匹配规则
                        if self._matches_patterns(node.name):
                            node.source_subscription = self.url
                            nodes.append(node)
                except Exception as e:
                    logger.debug(f"Failed to parse Vless URI: {e}")
        
        return nodes
    
    def _try_base64_decode(self, content: str) -> Optional[str]:
        """尝试Base64解码"""
        try:
            # 处理可能的URL安全Base64
            content = content.strip()
            # 填充
            padding = 4 - len(content) % 4
            if padding != 4:
                content += '=' * padding
            
            decoded = base64.b64decode(content).decode('utf-8')
            return decoded
        except:
            return None
    
    def _parse_vless_uri(self, uri: str) -> Optional[VlessNode]:
        """解析Vless URI为节点对象"""
        try:
            # vless://uuid@address:port?params#remarks
            if not uri.startswith('vless://'):
                return None
            
            # 移除前缀
            content = uri[8:]
            
            # 分离备注
            remarks = ""
            if '#' in content:
                content, remarks = content.split('#', 1)
                remarks = unquote(remarks)
            
            # 分离参数
            params_str = ""
            if '?' in content:
                content, params_str = content.split('?', 1)
            
            # 解析主体
            if '@' not in content:
                return None
            
            uuid, server_part = content.split('@', 1)
            
            # 解析地址和端口
            if ':' not in server_part:
                return None
            
            # 处理IPv6
            if server_part.startswith('['):
                end_idx = server_part.find(']')
                if end_idx == -1:
                    return None
                address = server_part[1:end_idx]
                port_part = server_part[end_idx + 1:]
                if port_part.startswith(':'):
                    port = int(port_part[1:])
                else:
                    return None
            else:
                address, port_str = server_part.rsplit(':', 1)
                port = int(port_str)
            
            # 解析参数
            network = "tcp"
            security = "none"
            host = None
            path = None
            sni = None
            tls = False
            
            if params_str:
                from urllib.parse import parse_qs
                params = parse_qs(params_str)
                
                network = params.get('type', ['tcp'])[0]
                security = params.get('security', ['none'])[0]
                host = params.get('host', [None])[0]
                path = params.get('path', [None])[0]
                sni = params.get('sni', [None])[0]
                
                if security in ['tls', 'xtls', 'reality']:
                    tls = True
            
            return VlessNode(
                uri=uri,
                name=remarks or f"{address}:{port}",
                address=address,
                port=port,
                uuid=uuid,
                network=network,
                security=security,
                host=host,
                path=path,
                sni=sni,
                tls=tls,
                source_subscription=self.url
            )
            
        except Exception as e:
            logger.debug(f"Parse Vless URI error: {e}")
            return None
    
    def _matches_patterns(self, name: str) -> bool:
        """检查节点名称是否匹配规则"""
        if not self.remarks_patterns:
            return True  # 没有规则则全部接受
        
        for pattern in self.remarks_patterns:
            if pattern in name or re.search(pattern, name):
                return True
        return False


# 全局订阅管理器
_global_subscription_manager: Optional[SubscriptionManager] = None


def get_subscription_manager() -> SubscriptionManager:
    """获取全局订阅管理器"""
    global _global_subscription_manager
    if _global_subscription_manager is None:
        _global_subscription_manager = SubscriptionManager()
    return _global_subscription_manager


async def init_subscriptions_from_env() -> SubscriptionManager:
    """从环境变量初始化订阅"""
    import os
    
    manager = get_subscription_manager()
    
    # 读取订阅URL
    sub_urls = os.environ.get('VLESS_SUBSCRIPTION_URLS', '')
    if sub_urls:
        # 支持多种分隔符
        urls = []
        for sep in ['\n', ',', ';']:
            if sep in sub_urls:
                urls = [u.strip() for u in sub_urls.split(sep) if u.strip()]
                break
        if not urls:
            urls = [sub_urls.strip()]
        
        # 读取匹配规则
        patterns_str = os.environ.get('VLESS_SUBSCRIPTION_PATTERNS', '')
        patterns = []
        if patterns_str:
            for sep in ['\n', ',', ';']:
                if sep in patterns_str:
                    patterns = [p.strip() for p in patterns_str.split(sep) if p.strip()]
                    break
            if not patterns:
                patterns = [patterns_str.strip()]
        
        # 添加订阅
        for url in urls:
            manager.add_subscription(url=url, remarks_patterns=patterns)
        
        # 立即获取
        await manager.fetch_all()
    
    return manager
