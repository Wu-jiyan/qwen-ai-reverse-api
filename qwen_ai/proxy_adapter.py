"""代理适配器 - 为 requests 库添加 Vless 代理支持

通过创建自定义的 HTTPAdapter 来支持 Vless 代理
"""

import asyncio
import socket
import ssl
import threading
import queue
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.connection import create_connection
from urllib3.util.ssl_ import create_urllib3_context

from .vless_proxy import VlessProxy, VlessProxyPool, get_proxy_pool, init_proxy_pool_from_env


class VlessProxyConnection:
    """Vless 代理连接包装器"""
    
    def __init__(self, proxy: VlessProxy, target_host: str, target_port: int):
        self.proxy = proxy
        self.target_host = target_host
        self.target_port = target_port
        self._socket: Optional[socket.socket] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._connected = False
    
    def connect(self, timeout: float = 30) -> socket.socket:
        """
        建立 Vless 代理连接并返回 socket
        
        Returns:
            已连接的 socket
        """
        if self._connected:
            return self._socket
        
        # 创建事件循环在线程中运行
        result_queue = queue.Queue()
        
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            
            try:
                reader, writer = loop.run_until_complete(
                    asyncio.wait_for(
                        self.proxy.create_connection(self.target_host, self.target_port),
                        timeout=timeout
                    )
                )
                
                self._reader = reader
                self._writer = writer
                
                # 获取底层 socket
                transport = writer.transport
                if hasattr(transport, 'get_extra_info'):
                    sock = transport.get_extra_info('socket')
                    if sock:
                        self._socket = sock
                    else:
                        # 对于 SSL 传输，获取原始 socket
                        sock = transport.get_extra_info('ssl_object')
                        if sock:
                            self._socket = sock
                
                # 如果没有获取到 socket，创建一个包装器
                if self._socket is None:
                    self._socket = VlessSocketWrapper(reader, writer)
                
                self._connected = True
                result_queue.put(('success', None))
                
                # 保持事件循环运行
                loop.run_forever()
                
            except Exception as e:
                result_queue.put(('error', e))
            finally:
                loop.close()
        
        self._thread = threading.Thread(target=run_async, daemon=True)
        self._thread.start()
        
        # 等待连接结果
        status, error = result_queue.get(timeout=timeout + 5)
        if status == 'error':
            raise ConnectionError(f'Failed to establish Vless connection: {error}')
        
        return self._socket
    
    def close(self):
        """关闭连接"""
        if self._writer:
            try:
                self._writer.close()
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self._writer.wait_closed(),
                        self._loop
                    )
            except:
                pass
        
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        self._connected = False


class VlessSocketWrapper:
    """Vless Socket 包装器 - 将 asyncio StreamReader/Writer 包装为 socket-like 对象"""
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        self._loop = asyncio.get_event_loop()
        self._closed = False
        
        # 设置 socket 选项
        self.family = socket.AF_INET
        self.type = socket.SOCK_STREAM
    
    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        """接收数据"""
        if self._closed:
            return b''
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._reader.read(bufsize),
                self._loop
            )
            return future.result(timeout=30)
        except Exception as e:
            raise socket.error(f'Recv error: {e}')
    
    def recv_into(self, buffer: bytearray, nbytes: int = 0, flags: int = 0) -> int:
        """接收数据到缓冲区"""
        if self._closed:
            return 0
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._reader.read(nbytes or len(buffer)),
                self._loop
            )
            data = future.result(timeout=30)
            buffer[:len(data)] = data
            return len(data)
        except Exception as e:
            raise socket.error(f'Recv error: {e}')
    
    def send(self, data: bytes, flags: int = 0) -> int:
        """发送数据"""
        if self._closed:
            raise socket.error('Socket is closed')
        
        try:
            self._writer.write(data)
            future = asyncio.run_coroutine_threadsafe(
                self._writer.drain(),
                self._loop
            )
            future.result(timeout=30)
            return len(data)
        except Exception as e:
            raise socket.error(f'Send error: {e}')
    
    def sendall(self, data: bytes, flags: int = 0):
        """发送所有数据"""
        self.send(data, flags)
    
    def close(self):
        """关闭 socket"""
        self._closed = True
        try:
            self._writer.close()
        except:
            pass
    
    def settimeout(self, timeout: float):
        """设置超时（不实现，由外部处理）"""
        pass
    
    def setblocking(self, flag: bool):
        """设置阻塞模式"""
        pass
    
    def shutdown(self, how: int):
        """关闭 socket 的一部分"""
        pass
    
    def fileno(self) -> int:
        """返回文件描述符"""
        return -1
    
    def getpeername(self):
        """获取对端地址"""
        return ('0.0.0.0', 0)
    
    def getsockname(self):
        """获取本地地址"""
        return ('0.0.0.0', 0)


class VlessHTTPAdapter(HTTPAdapter):
    """
    支持 Vless 代理的 HTTP Adapter
    
    使用方式:
        session = requests.Session()
        adapter = VlessHTTPAdapter(proxy_pool=pool)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
    """
    
    def __init__(self, proxy_pool: Optional[VlessProxyPool] = None, 
                 proxy_strategy: str = 'round_robin',
                 max_retries: int = 3,
                 **kwargs):
        """
        初始化 Vless HTTP Adapter
        
        Args:
            proxy_pool: Vless 代理池，为 None 则使用全局代理池
            proxy_strategy: 代理选择策略 ('round_robin' 或 'random')
            max_retries: 最大重试次数
        """
        self.proxy_pool = proxy_pool or get_proxy_pool()
        self.proxy_strategy = proxy_strategy
        self.max_retries = max_retries
        super().__init__(**kwargs)
    
    def get_connection(self, url: str, proxies: Optional[Dict[str, str]] = None):
        """
        获取连接
        
        如果配置了 Vless 代理，使用代理连接
        """
        # 检查是否有可用的 Vless 代理
        proxy = self.proxy_pool.get_proxy(self.proxy_strategy) if self.proxy_pool.count > 0 else None
        
        if proxy:
            # 使用 Vless 代理
            parsed = urlparse(url)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            
            try:
                conn = VlessProxyConnection(proxy, host, port)
                sock = conn.connect()
                
                # 标记代理使用成功
                proxy.mark_success()
                
                # 返回一个包装过的连接
                return VlessConnectionWrapper(sock, conn, parsed.scheme == 'https')
                
            except Exception as e:
                proxy.mark_fail()
                raise ConnectionError(f'Vless proxy connection failed: {e}')
        
        # 没有代理，使用默认连接
        return super().get_connection(url, proxies)
    
    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        """发送请求"""
        # 如果启用了 Vless 代理，禁用 urllib3 的代理处理
        if self.proxy_pool.count > 0:
            proxies = None
        
        return super().send(request, stream, timeout, verify, cert, proxies)


class VlessConnectionWrapper:
    """Vless 连接包装器 - 适配 urllib3 的连接接口"""
    
    def __init__(self, sock: socket.socket, conn: VlessProxyConnection, is_https: bool):
        self.sock = sock
        self._vless_conn = conn
        self.is_https = is_https
        self._ssl_context: Optional[ssl.SSLContext] = None
    
    def connect(self):
        """连接（已连接，直接返回）"""
        return self
    
    def close(self):
        """关闭连接"""
        self._vless_conn.close()
        try:
            self.sock.close()
        except:
            pass
    
    def send(self, data: bytes):
        """发送数据"""
        return self.sock.send(data)
    
    def recv(self, amt: int) -> bytes:
        """接收数据"""
        return self.sock.recv(amt)
    
    def settimeout(self, timeout: float):
        """设置超时"""
        self.sock.settimeout(timeout)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


class ProxyManager:
    """代理管理器 - 统一管理各种代理"""
    
    def __init__(self):
        self.vless_pool: Optional[VlessProxyPool] = None
        self.http_proxy: Optional[str] = None
        self.https_proxy: Optional[str] = None
        self._adapter: Optional[VlessHTTPAdapter] = None
    
    def init_from_env(self) -> 'ProxyManager':
        """从环境变量初始化"""
        import os
        
        # 初始化 Vless 代理池
        self.vless_pool = init_proxy_pool_from_env()
        
        # 读取 HTTP 代理设置
        self.http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        self.https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        
        return self
    
    def init_vless_from_file(self, filepath: str) -> 'ProxyManager':
        """从文件加载 Vless 代理"""
        if self.vless_pool is None:
            self.vless_pool = get_proxy_pool()
        self.vless_pool.add_proxies_from_file(filepath)
        return self
    
    def add_vless_proxy(self, uri: str) -> bool:
        """添加单个 Vless 代理"""
        if self.vless_pool is None:
            self.vless_pool = get_proxy_pool()
        return self.vless_pool.add_proxy(uri)
    
    def get_requests_proxies(self) -> Optional[Dict[str, str]]:
        """
        获取 requests 库使用的代理配置
        
        Returns:
            代理配置字典或 None
        """
        proxies = {}
        
        if self.http_proxy:
            proxies['http'] = self.http_proxy
        if self.https_proxy:
            proxies['https'] = self.https_proxy
        
        return proxies if proxies else None
    
    def create_session(self, use_vless: bool = True) -> requests.Session:
        """
        创建配置了代理的 requests Session
        
        Args:
            use_vless: 是否使用 Vless 代理
            
        Returns:
            配置好的 Session
        """
        session = requests.Session()
        
        if use_vless and self.vless_pool and self.vless_pool.count > 0:
            # 使用 Vless 代理
            adapter = VlessHTTPAdapter(proxy_pool=self.vless_pool)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            self._adapter = adapter
        else:
            # 使用普通 HTTP 代理
            proxies = self.get_requests_proxies()
            if proxies:
                session.proxies = proxies
        
        return session
    
    def get_stats(self) -> Dict[str, Any]:
        """获取代理统计信息"""
        stats = {
            'http_proxy': self.http_proxy,
            'https_proxy': self.https_proxy,
        }
        
        if self.vless_pool:
            stats['vless'] = self.vless_pool.get_stats()
        else:
            stats['vless'] = {'total': 0, 'healthy': 0, 'unhealthy': 0, 'proxies': []}
        
        return stats


# 全局代理管理器
_global_proxy_manager: Optional[ProxyManager] = None
_proxy_manager_lock = threading.Lock()


def get_proxy_manager() -> ProxyManager:
    """获取全局代理管理器（线程安全）"""
    global _global_proxy_manager
    if _global_proxy_manager is None:
        with _proxy_manager_lock:
            if _global_proxy_manager is None:
                _global_proxy_manager = ProxyManager()
    return _global_proxy_manager


def init_proxy_manager() -> ProxyManager:
    """初始化全局代理管理器（从环境变量，线程安全）"""
    global _global_proxy_manager
    with _proxy_manager_lock:
        if _global_proxy_manager is None:
            _global_proxy_manager = ProxyManager()
        # 检查是否已经初始化过
        if not hasattr(_global_proxy_manager, '_initialized') or not _global_proxy_manager._initialized:
            _global_proxy_manager.init_from_env()
            _global_proxy_manager._initialized = True
    return _global_proxy_manager
