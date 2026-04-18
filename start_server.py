#!/usr/bin/env python3
"""Start the OpenAI Compatible API Server for Qwen AI

支持代理功能，通过环境变量控制
"""

import argparse
import os
import sys
import asyncio
from pathlib import Path


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
                        if 'token' not in key.lower() and 'password' not in key.lower():
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
    parser = argparse.ArgumentParser(description="Start Qwen AI OpenAI Compatible API Server")
    parser.add_argument("--host", default=None, help="Host to bind (default: from env or 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: from env or 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--no-proxy", action="store_true", help="Disable proxy even if configured")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Qwen AI OpenAI Compatible API Server")
    print("=" * 60)
    
    # 加载环境变量
    load_env()
    
    # 获取配置
    host = args.host or os.environ.get('HOST', '0.0.0.0')
    port = args.port or int(os.environ.get('PORT', '8000'))
    enable_proxy = os.environ.get('ENABLE_PROXY', 'false').lower() == 'true'
    
    # 检查代理配置
    if enable_proxy and not args.no_proxy:
        sub_urls = os.environ.get('VLESS_SUBSCRIPTION_URLS', '')
        if sub_urls:
            print(f"\n[Proxy] 代理功能已启用")
            pattern = os.environ.get('VLESS_SUBSCRIPTION_PATTERNS', 'CF优选-电信')
            print(f"[Proxy] 匹配规则: {pattern}")
            
            # 初始化代理池
            try:
                asyncio.run(init_proxy_pool())
            except Exception as e:
                print(f"[Proxy] 警告: 代理池初始化失败: {e}")
        else:
            print("\n[Proxy] 警告: 代理功能已启用但未配置订阅URL")
            print("[Proxy] 请在 .env 文件中配置 VLESS_SUBSCRIPTION_URLS")
    else:
        if args.no_proxy:
            print("\n[Proxy] 代理功能已通过 --no-proxy 参数禁用")
        else:
            print("\n[Proxy] 代理功能未启用")
            print("[Proxy] 设置 ENABLE_PROXY=true 启用代理功能")
    
    print(f"\n[Server] 启动服务...")
    print(f"[Server] 监听地址: {host}:{port}")
    print(f"[Server] API文档: http://{host}:{port}/docs")
    print(f"[Server] 健康检查: http://{host}:{port}/health")
    print("=" * 60)
    
    import uvicorn
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=args.reload or os.environ.get('DEBUG', 'false').lower() == 'true',
        log_level="info"
    )


if __name__ == "__main__":
    main()
