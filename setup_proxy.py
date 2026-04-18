#!/usr/bin/env python3
"""Vless 代理配置脚本

帮助用户快速配置 Vless 订阅代理
"""

import os
import sys
import json


def print_header(text):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_step(step, text):
    """打印步骤"""
    print(f"\n[步骤 {step}] {text}")


def get_input(prompt, default=None):
    """获取用户输入"""
    if default:
        prompt = f"{prompt} (默认: {default}): "
    else:
        prompt = f"{prompt}: "
    
    value = input(prompt).strip()
    if not value and default:
        return default
    return value


def setup_subscription():
    """配置订阅"""
    print_header("Vless 订阅代理配置")
    
    print("""
本配置将帮助您设置 Vless 代理订阅功能。

功能说明：
1. 从订阅URL获取 Vless 节点
2. 按规则筛选节点（如 CF优选-电信）
3. 自动测试节点可用性
4. 存储可用节点到本地
5. API调用时随机使用可用节点
""")
    
    # 步骤1: 订阅URL
    print_step(1, "配置订阅 URL")
    print("请输入您的 Vless 订阅链接")
    print("示例: https://example.com/subscription")
    
    subscription_url = get_input("订阅 URL")
    
    if not subscription_url:
        print("错误: 订阅 URL 不能为空")
        return False
    
    # 步骤2: 节点匹配规则
    print_step(2, "配置节点匹配规则")
    print("""
节点匹配规则用于筛选订阅中的特定节点。
例如：
  - CF优选-电信  (匹配名称包含"CF优选-电信"的节点)
  - 美国         (匹配名称包含"美国"的节点)
  - .*香港.*     (使用正则表达式匹配)
""")
    
    pattern = get_input("节点匹配规则", "CF优选-电信")
    
    # 步骤3: 其他配置
    print_step(3, "其他配置")
    
    auto_refresh = get_input("启动时自动刷新订阅? (yes/no)", "yes")
    storage_file = get_input("节点存储文件", "vless_nodes.json")
    
    # 生成配置
    config = {
        "VLESS_SUBSCRIPTION_URLS": subscription_url,
        "VLESS_SUBSCRIPTION_PATTERNS": pattern,
        "VLESS_AUTO_REFRESH_ON_START": "true" if auto_refresh.lower() in ["yes", "y", "true"] else "false",
        "VLESS_STORAGE_FILE": storage_file,
    }
    
    # 保存到 .env 文件
    print_step(4, "保存配置")
    
    env_content = f"""# Vless 订阅配置
# 生成时间: {__import__('datetime').datetime.now().isoformat()}

# 订阅URL
VLESS_SUBSCRIPTION_URLS={subscription_url}

# 节点匹配规则
VLESS_SUBSCRIPTION_PATTERNS={pattern}

# 启动时自动刷新订阅
VLESS_AUTO_REFRESH_ON_START={config['VLESS_AUTO_REFRESH_ON_START']}

# 节点存储文件
VLESS_STORAGE_FILE={storage_file}
"""
    
    env_file = ".env"
    
    # 检查是否已存在 .env 文件
    if os.path.exists(env_file):
        backup = f"{env_file}.backup"
        print(f"备份现有配置到 {backup}")
        with open(env_file, 'r', encoding='utf-8') as f:
            existing = f.read()
        with open(backup, 'w', encoding='utf-8') as f:
            f.write(existing)
    
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"\n配置已保存到 {env_file}")
    
    # 显示配置摘要
    print_header("配置摘要")
    print(f"订阅 URL: {subscription_url}")
    print(f"匹配规则: {pattern}")
    print(f"自动刷新: {config['VLESS_AUTO_REFRESH_ON_START']}")
    print(f"存储文件: {storage_file}")
    
    print("""
使用方法：

1. 启动服务:
   python server.py

2. 查看代理统计:
   curl http://localhost:8000/v1/proxy/stats

3. 手动刷新订阅:
   curl -X POST http://localhost:8000/v1/proxy/refresh \\
     -H "Content-Type: application/json" \\
     -d '{"test_nodes": true}'

4. 查看可用节点:
   curl http://localhost:8000/v1/proxy/nodes

5. 测试节点:
   curl -X POST http://localhost:8000/v1/proxy/test \\
     -H "Content-Type: application/json" \\
     -d '{"pattern": "''' + pattern + '''"}'
""")
    
    return True


def test_configuration():
    """测试配置"""
    print_header("测试配置")
    
    try:
        # 检查依赖
        print("\n检查依赖...")
        
        try:
            import aiohttp
            print("  ✓ aiohttp")
        except ImportError:
            print("  ✗ aiohttp (请运行: pip install aiohttp)")
            return False
        
        try:
            import fastapi
            print("  ✓ fastapi")
        except ImportError:
            print("  ✗ fastapi")
            return False
        
        # 检查模块
        print("\n检查模块...")
        try:
            from qwen_ai.vless_proxy import SubscriptionProxyPool
            print("  ✓ vless_proxy")
        except Exception as e:
            print(f"  ✗ vless_proxy: {e}")
            return False
        
        try:
            from qwen_ai.subscription import SubscriptionManager
            print("  ✓ subscription")
        except Exception as e:
            print(f"  ✗ subscription: {e}")
            return False
        
        try:
            from qwen_ai.node_storage import NodeStorage
            print("  ✓ node_storage")
        except Exception as e:
            print(f"  ✗ node_storage: {e}")
            return False
        
        try:
            from qwen_ai.node_tester import NodeTester
            print("  ✓ node_tester")
        except Exception as e:
            print(f"  ✗ node_tester: {e}")
            return False
        
        print("\n✓ 所有检查通过！")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        return False


def main():
    """主函数"""
    print_header("Qwen AI Reverse API - Vless 代理配置工具")
    
    print("""
请选择操作：
1. 配置 Vless 订阅代理
2. 测试配置
3. 退出
""")
    
    choice = get_input("请输入选项 (1-3)", "1")
    
    if choice == "1":
        if setup_subscription():
            print("\n配置完成！")
            # 询问是否测试
            if get_input("是否测试配置? (yes/no)", "yes").lower() in ["yes", "y"]:
                test_configuration()
    elif choice == "2":
        test_configuration()
    else:
        print("退出")
        return
    
    print("\n感谢使用！")


if __name__ == "__main__":
    main()
