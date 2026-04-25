#!/usr/bin/env python3
"""Qwen AI 账号注册工具

使用方法:
    python register_account.py --email user@example.com --name username --password yourpass
    
    # 使用 IMAP 自动激活
    python register_account.py --email user@example.com --name username --password yourpass \
        --imap-host imap.qq.com --imap-port 993 --imap-user your@qq.com --imap-pass your_auth_code
"""

import argparse
import json
import sys
from typing import Optional

from qwen_ai.account_register import (
    QwenAccountRegister,
    IMAPVerification,
    register_account_auto
)


def print_header(text: str):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_success(text: str):
    """打印成功信息"""
    print(f"✓ {text}")


def print_error(text: str):
    """打印错误信息"""
    print(f"✗ {text}", file=sys.stderr)


def print_info(text: str):
    """打印信息"""
    print(f"  {text}")


def manual_mode(args):
    """手动激活模式"""
    print_header("手动激活模式")
    
    register = QwenAccountRegister(proxy=args.proxy)
    
    try:
        # 1. 注册
        print_info(f"正在注册账号: {args.email}")
        result = register.signup(args.email, args.name, args.password)
        print_success(f"注册成功！")
        
        # 显示激活链接
        activation_url = f"https://chat.qwen.ai/api/v1/auths/activate?id={result['id']}&token={result['token']}"
        print_info(f"激活链接: {activation_url}")
        print_info("请手动点击链接完成激活")
        
        # 保存到文件
        account_info = {
            'email': args.email,
            'name': args.name,
            'password': args.password,
            'activation_id': result['id'],
            'activation_token': result['token'],
            'activation_url': activation_url,
            'status': 'pending_activation'
        }
        
        filename = f"account_{args.email.replace('@', '_')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(account_info, f, indent=2, ensure_ascii=False)
        
        print_success(f"账号信息已保存到: {filename}")
        
        # 询问是否继续
        if args.auto_continue:
            input("\n请完成激活后按回车键继续...")
            
            # 登录
            print_info("正在登录...")
            jwt_token = register.signin(args.email, args.password)
            print_success(f"登录成功！")
            
            # 更新保存的信息
            account_info.update({
                'jwt_token': jwt_token,
                'status': 'completed'
            })
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(account_info, f, indent=2, ensure_ascii=False)
            
            print_success(f"完整信息已更新到: {filename}")
            print_info(f"JWT Token: {jwt_token}")
        
        return True
        
    except Exception as e:
        print_error(f"注册失败: {e}")
        return False


def auto_mode(args):
    """自动激活模式"""
    print_header("自动激活模式")
    
    imap_config = {
        'host': args.imap_host,
        'port': args.imap_port,
        'user': args.imap_user,
        'password': args.imap_pass
    }
    
    print_info(f"邮箱: {args.email}")
    print_info(f"IMAP: {args.imap_host}:{args.imap_port}")
    print_info(f"等待激活邮件（最多3分钟）...")
    
    result = register_account_auto(
        email=args.email,
        name=args.name,
        password=args.password,
        imap_config=imap_config,
        proxy=args.proxy
    )
    
    if result.success:
        print_success("注册成功！")
        print_info(f"JWT Token: {result.jwt_token}")
        
        # 保存到文件
        account_info = {
            'email': args.email,
            'name': args.name,
            'password': args.password,
            'jwt_token': result.jwt_token,
            'status': 'completed'
        }
        
        filename = f"account_{args.email.replace('@', '_')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(account_info, f, indent=2, ensure_ascii=False)
        
        print_success(f"账号信息已保存到: {filename}")
        return True
    else:
        print_error(f"注册失败: {result.error}")
        
        # 如果是等待激活状态，保存信息
        if result.activation_id and result.activation_token:
            account_info = {
                'email': args.email,
                'name': args.name,
                'password': args.password,
                'activation_id': result.activation_id,
                'activation_token': result.activation_token,
                'activation_url': f"https://chat.qwen.ai/api/v1/auths/activate?id={result.activation_id}&token={result.activation_token}",
                'status': 'pending_activation',
                'error': result.error
            }
            
            filename = f"account_{args.email.replace('@', '_')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(account_info, f, indent=2, ensure_ascii=False)
            
            print_info(f"部分信息已保存到: {filename}")
            print_info("您可以手动激活后继续")
        
        return False


def batch_mode(args):
    """批量注册模式"""
    print_header("批量注册模式")
    
    if not args.batch_file:
        print_error("批量模式需要提供 --batch-file 参数")
        return False
    
    try:
        with open(args.batch_file, 'r', encoding='utf-8') as f:
            accounts = json.load(f)
    except Exception as e:
        print_error(f"读取批量文件失败: {e}")
        return False
    
    results = []
    
    for i, account in enumerate(accounts, 1):
        print(f"\n[{i}/{len(accounts)}] 注册账号: {account.get('email', 'unknown')}")
        
        # 检查必要字段
        if not all(k in account for k in ['email', 'name', 'password']):
            print_error("账号信息不完整，跳过")
            results.append({**account, 'success': False, 'error': '信息不完整'})
            continue
        
        # 注册
        if args.imap_host and args.imap_user and args.imap_pass:
            # 自动模式
            imap_config = {
                'host': args.imap_host,
                'port': args.imap_port or 993,
                'user': args.imap_user,
                'password': args.imap_pass
            }
            
            result = register_account_auto(
                email=account['email'],
                name=account['name'],
                password=account['password'],
                imap_config=imap_config,
                proxy=args.proxy
            )
        else:
            # 手动模式
            register = QwenAccountRegister(proxy=args.proxy)
            try:
                signup_result = register.signup(
                    account['email'],
                    account['name'],
                    account['password']
                )
                result = type('Result', (), {
                    'success': False,
                    'email': account['email'],
                    'password': account['password'],
                    'error': '等待手动激活',
                    'activation_id': signup_result.get('id'),
                    'activation_token': signup_result.get('token'),
                    'jwt_token': None
                })()
            except Exception as e:
                result = type('Result', (), {
                    'success': False,
                    'email': account['email'],
                    'password': account['password'],
                    'error': str(e),
                    'activation_id': None,
                    'activation_token': None,
                    'jwt_token': None
                })()
        
        # 保存结果
        results.append({
            'email': result.email,
            'name': account['name'],
            'password': result.password,
            'success': result.success,
            'error': result.error if not result.success else None,
            'jwt_token': result.jwt_token if result.success else None,
            'activation_id': result.activation_id if not result.success else None,
            'activation_token': result.activation_token if not result.success else None
        })
        
        # 保存单个账号信息
        filename = f"account_{result.email.replace('@', '_')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results[-1], f, indent=2, ensure_ascii=False)
        
        if result.success:
            print_success(f"注册成功: {result.email}")
        else:
            print_error(f"注册失败: {result.email} - {result.error}")
    
    # 保存汇总结果
    summary_file = "batch_results.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total': len(accounts),
            'success': sum(1 for r in results if r['success']),
            'failed': sum(1 for r in results if not r['success']),
            'results': results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n批量注册完成！")
    print_info(f"成功: {sum(1 for r in results if r['success'])}/{len(accounts)}")
    print_info(f"结果已保存到: {summary_file}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Qwen AI 账号注册工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 手动模式（需要手动点击激活链接）
  python register_account.py -e user@example.com -n username -p password
  
  # 自动模式（使用 IMAP 自动读取激活邮件）
  python register_account.py -e user@example.com -n username -p password \\
      --imap-host imap.qq.com --imap-user your@qq.com --imap-pass your_auth_code
  
  # 批量注册
  python register_account.py --batch-file accounts.json \\
      --imap-host imap.qq.com --imap-user your@qq.com --imap-pass your_auth_code

批量文件格式 (accounts.json):
  [
    {"email": "user1@example.com", "name": "user1", "password": "pass1"},
    {"email": "user2@example.com", "name": "user2", "password": "pass2"}
  ]
        """
    )
    
    # 基本参数
    parser.add_argument('-e', '--email', help='邮箱地址')
    parser.add_argument('-n', '--name', help='用户名')
    parser.add_argument('-p', '--password', help='密码')
    parser.add_argument('--proxy', help='代理地址，如 http://proxy:port')
    
    # IMAP 参数（自动模式）
    parser.add_argument('--imap-host', help='IMAP 服务器地址')
    parser.add_argument('--imap-port', type=int, default=993, help='IMAP 端口（默认：993）')
    parser.add_argument('--imap-user', help='IMAP 用户名')
    parser.add_argument('--imap-pass', help='IMAP 密码或授权码')
    
    # 其他选项
    parser.add_argument('--auto-continue', action='store_true',
                        help='手动模式下，激活后自动继续登录')
    parser.add_argument('--batch-file', help='批量注册文件（JSON 格式）')
    
    args = parser.parse_args()
    
    # 检查参数
    if args.batch_file:
        # 批量模式
        success = batch_mode(args)
    elif args.email and args.name and args.password:
        # 单账号模式
        if args.imap_host and args.imap_user and args.imap_pass:
            success = auto_mode(args)
        else:
            success = manual_mode(args)
    else:
        parser.print_help()
        return
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
