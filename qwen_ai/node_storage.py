"""节点存储模块 - 本地持久化存储可用节点

支持JSON文件存储，自动加载和保存
"""

import json
import os
import asyncio
import logging
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from datetime import datetime, timedelta

from .subscription import VlessNode

logger = logging.getLogger(__name__)


class NodeStorage:
    """节点存储管理器"""
    
    DEFAULT_STORAGE_FILE = "vless_nodes.json"
    
    def __init__(self, storage_file: Optional[str] = None):
        self.storage_file = storage_file or self.DEFAULT_STORAGE_FILE
        self._cache: Dict[str, VlessNode] = {}
        self._lock = asyncio.Lock()
        self._last_save = datetime.min
        self._dirty = False
    
    async def load(self) -> Dict[str, VlessNode]:
        """从文件加载节点"""
        async with self._lock:
            if not os.path.exists(self.storage_file):
                logger.info(f"Storage file {self.storage_file} not found, starting with empty cache")
                self._cache = {}
                return self._cache
            
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                nodes = {}
                for identifier, node_data in data.get('nodes', {}).items():
                    try:
                        node = VlessNode.from_dict(node_data)
                        nodes[identifier] = node
                    except Exception as e:
                        logger.debug(f"Failed to load node {identifier}: {e}")
                
                self._cache = nodes
                logger.info(f"Loaded {len(nodes)} nodes from {self.storage_file}")
                return nodes
                
            except Exception as e:
                logger.error(f"Failed to load storage file: {e}")
                self._cache = {}
                return self._cache
    
    async def save(self, nodes: Optional[Dict[str, VlessNode]] = None, force: bool = False):
        """
        保存节点到文件
        
        Args:
            nodes: 要保存的节点，为None则保存缓存
            force: 是否强制保存（忽略脏标记）
        """
        async with self._lock:
            if nodes is not None:
                self._cache = nodes
            
            if not force and not self._dirty:
                # 检查自动保存间隔
                elapsed = (datetime.now() - self._last_save).total_seconds()
                if elapsed < 60:  # 至少60秒保存一次
                    return
            
            try:
                data = {
                    'version': '1.0',
                    'updated_at': datetime.now().isoformat(),
                    'nodes': {
                        identifier: node.to_dict()
                        for identifier, node in self._cache.items()
                    }
                }
                
                # 先写入临时文件，然后原子替换
                temp_file = self.storage_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # 原子替换
                if os.path.exists(self.storage_file):
                    os.replace(temp_file, self.storage_file)
                else:
                    os.rename(temp_file, self.storage_file)
                
                self._last_save = datetime.now()
                self._dirty = False
                logger.debug(f"Saved {len(self._cache)} nodes to {self.storage_file}")
                
            except Exception as e:
                logger.error(f"Failed to save storage file: {e}")
    
    async def update_node(self, node: VlessNode, auto_save: bool = True):
        """更新单个节点"""
        async with self._lock:
            self._cache[node.identifier] = node
            self._dirty = True
        
        if auto_save:
            await self.save()
    
    async def update_nodes(self, nodes: List[VlessNode], auto_save: bool = True):
        """批量更新节点"""
        async with self._lock:
            for node in nodes:
                # 保留已有节点的状态
                if node.identifier in self._cache:
                    existing = self._cache[node.identifier]
                    node.is_available = existing.is_available
                    node.fail_count = existing.fail_count
                    node.success_count = existing.success_count
                    node.average_latency = existing.average_latency
                    node.last_tested = existing.last_tested
                
                self._cache[node.identifier] = node
            self._dirty = True
        
        if auto_save:
            await self.save()
    
    async def mark_node_result(self, identifier: str, success: bool, latency: float = 0, auto_save: bool = True):
        """标记节点使用结果"""
        async with self._lock:
            if identifier in self._cache:
                node = self._cache[identifier]
                if success:
                    node.mark_success(latency)
                else:
                    node.mark_fail()
                self._dirty = True
        
        if auto_save:
            await self.save()
    
    def get_node(self, identifier: str) -> Optional[VlessNode]:
        """获取单个节点"""
        return self._cache.get(identifier)
    
    def get_all_nodes(self) -> Dict[str, VlessNode]:
        """获取所有节点"""
        return self._cache.copy()
    
    def get_available_nodes(self) -> List[VlessNode]:
        """获取所有可用节点"""
        return [n for n in self._cache.values() if n.is_available]
    
    def get_nodes_by_pattern(self, pattern: str) -> List[VlessNode]:
        """按名称模式获取节点"""
        import re
        return [
            n for n in self._cache.values()
            if pattern in n.name or re.search(pattern, n.name)
        ]
    
    async def remove_node(self, identifier: str, auto_save: bool = True):
        """移除节点"""
        async with self._lock:
            if identifier in self._cache:
                del self._cache[identifier]
                self._dirty = True
        
        if auto_save:
            await self.save()
    
    async def clean_expired(self, max_age_days: int = 7, auto_save: bool = True) -> int:
        """
        清理过期节点
        
        Args:
            max_age_days: 最大保留天数
            
        Returns:
            清理的节点数量
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        to_remove = []
        
        async with self._lock:
            for identifier, node in self._cache.items():
                # 检查最后测试时间
                if node.last_tested:
                    try:
                        last_tested = datetime.fromisoformat(node.last_tested)
                        if last_tested < cutoff and not node.is_available:
                            to_remove.append(identifier)
                    except:
                        pass
        
        for identifier in to_remove:
            await self.remove_node(identifier, auto_save=False)
        
        if to_remove and auto_save:
            await self.save()
        
        logger.info(f"Cleaned {len(to_remove)} expired nodes")
        return len(to_remove)
    
    async def merge_with_subscription(self, sub_nodes: List[VlessNode], auto_save: bool = True) -> tuple:
        """
        合并订阅节点与本地存储
        
        Args:
            sub_nodes: 从订阅获取的节点
            
        Returns:
            (新增数量, 更新数量, 移除数量)
        """
        async with self._lock:
            added = 0
            updated = 0
            
            # 获取订阅中的标识符
            sub_identifiers = {n.identifier for n in sub_nodes}
            
            # 更新或添加节点
            for node in sub_nodes:
                if node.identifier in self._cache:
                    # 更新现有节点（保留状态）
                    existing = self._cache[node.identifier]
                    node.is_available = existing.is_available
                    node.fail_count = existing.fail_count
                    node.success_count = existing.success_count
                    node.average_latency = existing.average_latency
                    node.last_tested = existing.last_tested
                    updated += 1
                else:
                    added += 1
                
                self._cache[node.identifier] = node
            
            # 标记不在订阅中的节点（但不删除，保留历史）
            removed = 0
            for identifier in list(self._cache.keys()):
                if identifier not in sub_identifiers:
                    # 可选：标记为不可用或删除
                    # self._cache[identifier].is_available = False
                    pass
            
            self._dirty = True
        
        if auto_save:
            await self.save()
        
        logger.info(f"Merged subscription: {added} added, {updated} updated")
        return added, updated, removed
    
    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计"""
        total = len(self._cache)
        available = len(self.get_available_nodes())
        
        # 按来源统计
        by_source = {}
        for node in self._cache.values():
            source = node.source_subscription or "unknown"
            if source not in by_source:
                by_source[source] = {'total': 0, 'available': 0}
            by_source[source]['total'] += 1
            if node.is_available:
                by_source[source]['available'] += 1
        
        return {
            'total_nodes': total,
            'available_nodes': available,
            'unavailable_nodes': total - available,
            'by_source': by_source,
            'storage_file': self.storage_file,
            'last_save': self._last_save.isoformat() if self._last_save != datetime.min else None
        }


# 全局存储实例
_global_storage: Optional[NodeStorage] = None


def get_node_storage(storage_file: Optional[str] = None) -> NodeStorage:
    """获取全局存储实例"""
    global _global_storage
    if _global_storage is None:
        _global_storage = NodeStorage(storage_file)
    return _global_storage


async def init_node_storage(storage_file: Optional[str] = None) -> NodeStorage:
    """初始化并加载节点存储"""
    storage = get_node_storage(storage_file)
    await storage.load()
    return storage
