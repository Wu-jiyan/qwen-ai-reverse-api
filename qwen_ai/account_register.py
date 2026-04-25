"""Qwen AI 账号自动注册模块

实现自动注册、激活、登录获取 JWT Token 的完整流程
"""

import re
import time
import hashlib
import imaplib
import email
from typing import Optional, Dict
from dataclasses import dataclass

import requests


# Qwen AI API 配置
QWEN_BASE_URL = "https://chat.qwen.ai"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass
class RegistrationResult:
    """注册结果"""
    success: bool
    email: str
    password: str
    jwt_token: Optional[str] = None
    error: Optional[str] = None
    activation_id: Optional[str] = None
    activation_token: Optional[str] = None


class QwenAccountRegister:
    """Qwen AI 账号注册器"""
    
    def __init__(self, proxy: Optional[str] = None):
        """
        初始化注册器
        
        Args:
            proxy: 代理地址，如 http://proxy:port
        """
        self.proxy = proxy
        self.session = requests.Session()
        
        if proxy:
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }
        
        # 设置默认请求头
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'source': 'web',
            'version': '0.2.35'
        })
    
    def _sha256(self, text: str) -> str:
        """计算 SHA-256 哈希"""
        return hashlib.sha256(text.encode()).hexdigest()
    
    def signup(self, email: str, name: str, password: str) -> Dict[str, str]:
        """
        注册账号
        
        Args:
            email: 邮箱地址
            name: 用户名
            password: 密码
            
        Returns:
            包含 id 和 token 的字典
        """
        password_hash = self._sha256(password)
        
        headers = {
            'Content-Type': 'application/json',
            'Referer': f'{QWEN_BASE_URL}/auth?mode=register',
            'Origin': QWEN_BASE_URL
        }
        
        data = {
            'name': name,
            'email': email,
            'password': password_hash,
            'agree': True,
            'profile_image_url': '/favicon.png',
            'oauth_sub': '',
            'oauth_token': '',
            'module': 'chat'
        }
        
        resp = self.session.post(
            f'{QWEN_BASE_URL}/api/v1/auths/signup',
            headers=headers,
            json=data
        )
        
        if resp.status_code != 200:
            print(f"[Register] 注册失败: {resp.status_code}")
            print(f"[Register] 响应: {resp.text[:500]}")
            raise Exception(f"注册失败: {resp.status_code} - {resp.text[:200]}")
        
        try:
            result = resp.json()
        except Exception as e:
            print(f"[Register] 解析响应失败: {e}")
            print(f"[Register] 原始响应: {resp.text[:500]}")
            raise Exception(f"解析响应失败: {resp.text[:200]}")
        
        return {
            'id': result.get('id'),
            'token': result.get('token')
        }
    
    def activate(self, activation_id: str, activation_token: str) -> bool:
        """
        激活账号
        
        Args:
            activation_id: 激活 ID
            activation_token: 激活 Token
            
        Returns:
            是否激活成功
        """
        url = f'{QWEN_BASE_URL}/api/v1/auths/activate'
        params = {
            'id': activation_id,
            'token': activation_token
        }
        
        resp = self.session.get(url, params=params, allow_redirects=False)
        
        # 成功返回 302 或 200
        return resp.status_code in [302, 200]
    
    def signin(self, email: str, password: str) -> str:
        """
        登录获取 JWT Token
        
        Args:
            email: 邮箱地址
            password: 密码
            
        Returns:
            JWT Token
        """
        password_hash = self._sha256(password)
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            'email': email,
            'password': password_hash
        }
        
        resp = self.session.post(
            f'{QWEN_BASE_URL}/api/v1/auths/signin',
            headers=headers,
            json=data
        )
        resp.raise_for_status()
        
        result = resp.json()
        return result.get('token')
    
    def register_complete(
        self,
        email: str,
        name: str,
        password: str,
        activation_id: Optional[str] = None,
        activation_token: Optional[str] = None
    ) -> RegistrationResult:
        """
        完整注册流程
        
        Args:
            email: 邮箱地址
            name: 用户名
            password: 密码
            activation_id: 激活 ID（可选）
            activation_token: 激活 Token（可选）
            
        Returns:
            注册结果
        """
        try:
            # 1. 注册
            print(f"[Register] 正在注册账号: {email}")
            signup_result = self.signup(email, name, password)
            print(f"[Register] 注册成功，ID: {signup_result['id']}")
            
            # 如果没有提供激活信息，返回等待激活状态
            if not activation_id or not activation_token:
                return RegistrationResult(
                    success=False,
                    email=email,
                    password=password,
                    error="需要手动激活",
                    activation_id=signup_result.get('id'),
                    activation_token=signup_result.get('token')
                )
            
            # 2. 激活
            print(f"[Register] 正在激活账号...")
            if not self.activate(activation_id, activation_token):
                return RegistrationResult(
                    success=False,
                    email=email,
                    password=password,
                    error="激活失败"
                )
            print(f"[Register] 激活成功")
            
            # 3. 登录获取 JWT
            print(f"[Register] 正在登录获取 JWT...")
            jwt_token = self.signin(email, password)
            print(f"[Register] 登录成功")
            
            return RegistrationResult(
                success=True,
                email=email,
                password=password,
                jwt_token=jwt_token
            )
            
        except Exception as e:
            return RegistrationResult(
                success=False,
                email=email,
                password=password,
                error=str(e)
            )


class IMAPVerification:
    """IMAP 邮箱验证"""
    
    def __init__(
        self,
        imap_host: str,
        imap_port: int,
        imap_user: str,
        imap_password: str,
        use_ssl: bool = True
    ):
        """
        初始化 IMAP 连接
        
        Args:
            imap_host: IMAP 服务器地址
            imap_port: IMAP 端口
            imap_user: 邮箱用户名
            imap_password: 邮箱密码或授权码
            use_ssl: 是否使用 SSL
        """
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.imap_user = imap_user
        self.imap_password = imap_password
        self.use_ssl = use_ssl
        self.mail = None
    
    def connect(self) -> bool:
        """连接 IMAP 服务器"""
        try:
            if self.use_ssl:
                self.mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                self.mail = imaplib.IMAP4(self.imap_host, self.imap_port)
            
            self.mail.login(self.imap_user, self.imap_password)
            return True
        except Exception as e:
            print(f"[IMAP] 连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开 IMAP 连接"""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
            except:
                pass
    
    def wait_for_activation_email(
        self,
        target_email: str,
        timeout: int = 180,
        check_interval: int = 5
    ) -> Optional[Dict[str, str]]:
        """
        等待并读取激活邮件
        
        Args:
            target_email: 目标邮箱地址
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）
            
        Returns:
            包含 id 和 token 的字典，超时返回 None
        """
        if not self.connect():
            return None
        
        try:
            self.mail.select('inbox')
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # 搜索未读邮件
                _, messages = self.mail.search(None, 'UNSEEN')
                
                if messages[0]:
                    msg_nums = messages[0].split()
                    
                    # 检查最近的 10 封邮件
                    for num in msg_nums[-10:]:
                        _, msg_data = self.mail.fetch(num, '(RFC822)')
                        
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                
                                # 获取邮件内容
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        content_type = part.get_content_type()
                                        if content_type == "text/html" or content_type == "text/plain":
                                            try:
                                                body += part.get_payload(decode=True).decode('utf-8')
                                            except:
                                                pass
                                else:
                                    try:
                                        body = msg.get_payload(decode=True).decode('utf-8')
                                    except:
                                        pass
                                
                                # 检查是否包含目标邮箱
                                if target_email.split('@')[0] in body:
                                    # 提取激活链接
                                    match = re.search(
                                        r'/api/v1/auths/activate\?id=([a-f0-9-]+)&token=([a-f0-9]+)',
                                        body
                                    )
                                    
                                    if match:
                                        activation_id = match.group(1)
                                        activation_token = match.group(2)
                                        
                                        print(f"[IMAP] 找到激活邮件: {target_email}")
                                        return {
                                            'id': activation_id,
                                            'token': activation_token
                                        }
                
                print(f"[IMAP] 等待激活邮件... ({int(time.time() - start_time)}s)")
                time.sleep(check_interval)
            
            print(f"[IMAP] 等待超时")
            return None
            
        finally:
            self.disconnect()


def register_account_auto(
    email: str,
    name: str,
    password: str,
    imap_config: Optional[Dict] = None,
    proxy: Optional[str] = None
) -> RegistrationResult:
    """
    全自动注册账号（需要 IMAP 配置）
    
    Args:
        email: 邮箱地址
        name: 用户名
        password: 密码
        imap_config: IMAP 配置
        proxy: 代理地址
        
    Returns:
        注册结果
    """
    register = QwenAccountRegister(proxy=proxy)
    
    try:
        # 1. 注册
        print(f"[AutoRegister] 正在注册: {email}")
        signup_result = register.signup(email, name, password)
        print(f"[AutoRegister] 注册成功，等待激活邮件...")
        
        # 2. 等待激活邮件
        if not imap_config:
            return RegistrationResult(
                success=False,
                email=email,
                password=password,
                error="未提供 IMAP 配置，无法自动读取邮件",
                activation_id=signup_result.get('id'),
                activation_token=signup_result.get('token')
            )
        
        imap = IMAPVerification(
            imap_host=imap_config['host'],
            imap_port=imap_config['port'],
            imap_user=imap_config['user'],
            imap_password=imap_config['password']
        )
        
        activation_info = imap.wait_for_activation_email(email, timeout=180)
        
        if not activation_info:
            return RegistrationResult(
                success=False,
                email=email,
                password=password,
                error="未收到激活邮件或超时",
                activation_id=signup_result.get('id'),
                activation_token=signup_result.get('token')
            )
        
        # 3. 激活
        print(f"[AutoRegister] 正在激活...")
        if not register.activate(activation_info['id'], activation_info['token']):
            return RegistrationResult(
                success=False,
                email=email,
                password=password,
                error="激活失败"
            )
        print(f"[AutoRegister] 激活成功")
        
        # 4. 登录获取 JWT
        print(f"[AutoRegister] 正在登录获取 JWT...")
        jwt_token = register.signin(email, password)
        print(f"[AutoRegister] 完成！")
        
        return RegistrationResult(
            success=True,
            email=email,
            password=password,
            jwt_token=jwt_token
        )
        
    except Exception as e:
        return RegistrationResult(
            success=False,
            email=email,
            password=password,
            error=str(e)
        )


# 示例使用
if __name__ == "__main__":
    # 示例：手动激活模式
    print("=" * 60)
    print("示例：手动激活模式")
    print("=" * 60)
    
    register = QwenAccountRegister()
    
    email = "your_email@example.com"
    name = "your_username"
    password = "your_password"
    
    try:
        result = register.signup(email, name, password)
        print(f"注册成功！")
        print(f"激活链接: {QWEN_BASE_URL}/api/v1/auths/activate?id={result['id']}&token={result['token']}")
        print(f"请手动点击链接激活，然后继续...")
        
        input("按回车键继续（激活后）...")
        
        jwt = register.signin(email, password)
        print(f"JWT Token: {jwt}")
        
    except Exception as e:
        print(f"错误: {e}")
