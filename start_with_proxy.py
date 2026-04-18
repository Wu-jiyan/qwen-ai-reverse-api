#!/usr/bin/env python3
"""带代理的启动脚本

自动加载环境变量并启动服务
"""

import os
import sys
import asyncio
from pathlib import Path

# 加载 .env 文件
def load_env():
    """加载环境变量"""
    env_file = Path(__file__).parent / ".env"
    
    if env_file.exists():
        print(f"[Config] 加载配置文件: {env_file}")
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"\'')
                    if key and value:
                        os.environ[key] = value
                        print(f"[Config] {key}={value[:50]}{'...' if len(value) > 50 else ''}")
    else:
        print("[Config] 未找到 .env 文件，使用默认配置")


async def init_proxy_pool():
    """初始化代理池"""
    try:
        from qwen_ai.vless_proxy import init_subscription_pool_from_env
        
        print("[Proxy] 初始化订阅代理池...")
        pool = await init_subscription_pool_from_env()
        
        stats = pool.get_stats()
        print(f"[Proxy] 代理池初始化完成")
        print(f"[Proxy] 当前规则: {stats.get('pattern', 'N/A')}")
        print(f"[Proxy] 可用节点: {stats.get('current_pattern', {}).get('available', 0)}")
        
        return pool
    except Exception as e:
        print(f"[Proxy] 代理池初始化失败: {e}")
        return None


def main():
    """主函数"""
    print("=" * 60)
    print("Qwen AI Reverse API - 带代理支持")
    print("=" * 60)
    
    # 加载环境变量
    load_env()
    
    # 检查订阅配置
    sub_urls = os.environ.get('VLESS_SUBSCRIPTION_URLS', '')
    if sub_urls:
        print(f"\n[Proxy] 订阅URL已配置")
        pattern = os.environ.get('VLESS_SUBSCRIPTION_PATTERNS', 'CF优选-电信')
        print(f"[Proxy] 匹配规则: {pattern}")
    else:
        print("\n[Proxy] 警告: 未配置订阅URL，代理功能将不可用")
        print("[Proxy] 请运行: python setup_proxy.py")
    
    # 启动服务
    print("\n[Server] 启动服务...")
    
    import uvicorn
    
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', '8000'))
    
    print(f"[Server] 监听地址: {host}:{port}")
    print(f"[Server] API文档: http://{host}:{port}/docs")
    print("=" * 60)
    
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=os.environ.get('DEBUG', 'false').lower() == 'true'
    )


if __name__ == "__main__":
    main()
