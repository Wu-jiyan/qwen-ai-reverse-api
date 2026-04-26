# Qwen AI OpenAI Compatible API

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

基于 Qwen AI (chat.qwen.ai) 的逆向 API，提供 OpenAI 兼容接口。

## 🔗 相关项目

- [DeepSeek Reverse API](https://github.com/Wu-jiyan/deepseek-reverse-api) - DeepSeek 网页端 逆向 API

## ✨ 功能特性

- 🔌 **OpenAI 兼容** - 与 OpenAI SDK 完全兼容的接口
- 🚀 **流式响应** - 实时流式输出，低延迟
- 💬 **上下文支持** - 多轮对话，保持对话连贯性
- 🧠 **思考过程** - 展示模型的推理思考过程
- 🎨 **图片生成** - 支持 Qwen 的图片生成功能
- 🔄 **Token 轮询** - 多 Token 随机负载均衡
- ✅ **健康检查** - Token 可用性检测接口
- 🌐 **Vless 代理池** - 支持从订阅 URL 获取和管理 Vless 节点
- 📍 **节点筛选** - 按规则筛选节点（如 CF优选-电信）
- 🔍 **健康检测** - 自动测试节点可用性和延迟
- 📊 **代理管理** - 完整的代理池管理 API

## 📦 安装

### 环境要求
- Python 3.8+

### 安装依赖

```bash
pip install -r requirements.txt
```

## 🚀 快速开始

### 1. 快速配置

#### 1.1 获取 JWT Token

![获取Token步骤](docs/1.png)
1. 访问 https://chat.qwen.ai 并登录账号
2. 按 F12 打开浏览器开发者工具
3. 进入 **Application** → **Local Storage** → **https://chat.qwen.ai**
4. 复制 `token` 键的值

#### 1.2 创建 .env 文件

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，填写你的配置
```

### 3. 启动服务

```bash
python start_server.py
```

**启动参数：**
| 参数 | 说明 |
|------|------|
| `--host` | 监听地址（默认：0.0.0.0） |
| `--port` | 监听端口（默认：8000） |
| `--reload` | 开发模式自动重载 |
| `--no-proxy` | 禁用代理功能 |

**启用代理功能：**
```bash
# 在 .env 文件中设置
ENABLE_PROXY=true

# 启动服务
python start_server.py
```

### 3. 测试 API

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.5-plus",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## 🎬 DEMO 演示

### 验明正身
![验明正身](docs/2.png)

### 多轮对话
![多轮对话](docs/3.png)

### 画图功能
![画图功能](docs/4.png)

### 深度思考
![深度思考](docs/5.png)

## 🔧 账号工具

### 获取 JWT Token

如果你已有账号，可以直接获取 JWT Token：

```bash
# 登录获取 JWT
python get_jwt.py -e your_email@example.com -p your_password

# 使用代理
python get_jwt.py -e your_email@example.com -p your_password --proxy http://proxy:port
```

如果账号需要激活，脚本会显示激活链接并保存激活信息。

### 账号注册

提供自动注册 Qwen AI 账号的功能，支持手动激活和 IMAP 自动激活。

### 手动注册模式

```bash
# 注册账号（需要手动点击激活链接）
python register_account.py -e your_email@example.com -n your_name -p your_password

# 注册并等待激活后继续
python register_account.py -e your_email@example.com -n your_name -p your_password --auto-continue
```

### 自动注册模式（需要 IMAP）

```bash
# 使用 IMAP 自动读取激活邮件
python register_account.py -e your_email@example.com -n your_name -p your_password \
    --imap-host imap.qq.com \
    --imap-user your_qq@qq.com \
    --imap-pass your_auth_code
```

### 批量注册

创建 `accounts.json` 文件：
```json
[
  {"email": "user1@example.com", "name": "user1", "password": "pass1"},
  {"email": "user2@example.com", "name": "user2", "password": "pass2"}
]
```

执行批量注册：
```bash
python register_account.py --batch-file accounts.json \
    --imap-host imap.qq.com \
    --imap-user your_qq@qq.com \
    --imap-pass your_auth_code
```

### 注册结果

注册成功后会生成 `account_xxx.json` 文件，包含：
- JWT Token（可直接用于 API 调用）
- 账号信息

JWT Token 可以直接用于 API 认证：
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.5-plus",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## 📖 API 文档

### 对话补全

```http
POST /v1/chat/completions
```

**请求头**
| 参数 | 说明 |
|------|------|
| Authorization | Bearer Token，支持单 Token 或多 Token（逗号分隔） |
| Content-Type | application/json |

**请求体**
```json
{
  "model": "qwen3.5-plus",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "stream": false,
  "temperature": 0.7
}
```

**参数说明**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 模型名称，如 qwen3.5-plus |
| messages | array | 是 | 消息列表 |
| stream | boolean | 否 | 是否流式输出，默认 false |
| temperature | float | 否 | 温度参数，默认 null |

### 自动删除对话

设置 `AUTO_DELETE_CHAT=true` 环境变量后，每次对话完成时会自动删除网页对话记录，保持账户清洁。

```bash
# .env 文件配置
AUTO_DELETE_CHAT=true
```

### Token 健康检查

```http
POST /v1/tokens/health
GET /v1/tokens/health?tokens=token1,token2
```

**请求体**
```json
{
  "tokens": "jwt_token_1,jwt_token_2"
}
```

**响应**
```json
{
  "total": 2,
  "healthy": 1,
  "unhealthy": 1,
  "results": [
    {
      "token": "eyJhbGci...",
      "status": "healthy",
      "valid": true
    },
    {
      "token": "invalid...",
      "status": "unhealthy",
      "valid": false,
      "error": "Token expired"
    }
  ]
}
```

### 获取模型列表

```http
GET /v1/models
```

## 💻 使用示例

### Python

```python
import requests

url = "http://localhost:8080/v1/chat/completions"
headers = {"Authorization": "Bearer YOUR_JWT_TOKEN"}

data = {
    "model": "qwen3.5-plus",
    "messages": [{"role": "user", "content": "Hello"}]
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

### 流式响应

```python
import requests

url = "http://localhost:8080/v1/chat/completions"
headers = {"Authorization": "Bearer YOUR_JWT_TOKEN"}

data = {
    "model": "qwen3.5-plus",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": True
}

response = requests.post(url, headers=headers, json=data, stream=True)
for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

### 上下文对话

```python
messages = [
    {"role": "user", "content": "My name is Alice"},
    {"role": "assistant", "content": "Hello Alice!"},
    {"role": "user", "content": "What is my name?"}
]

data = {
    "model": "qwen3.5-plus",
    "messages": messages
}

# 模型会回答 "Your name is Alice"
```

### 多 Token 轮询

```python
# 使用多个 Token，自动随机选择
tokens = "token1,token2,token3"
headers = {"Authorization": f"Bearer {tokens}"}
```

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="YOUR_JWT_TOKEN"
)

response = client.chat.completions.create(
    model="qwen3.5-plus",
    messages=[{"role": "user", "content": "Hello"}]
)

print(response.choices[0].message.content)
```

## 🔧 配置选项

### 启动参数

```bash
python start_server.py --host 0.0.0.0 --port 8080
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| --host | 0.0.0.0 | 监听地址 |
| --port | 8000 | 监听端口 |
| --reload | False | 开发模式自动重载 |

### 代理配置

本项目支持 Vless 协议代理池，可用于 IP 轮换和访问优化。

#### 启用代理

在 `.env` 文件中设置：

```bash
# 启用代理功能
ENABLE_PROXY=true

# 配置订阅URL（支持多个，用逗号分隔）
VLESS_SUBSCRIPTION_URLS="https://example.com/subscription"

# 节点匹配规则（如 CF优选-电信）
VLESS_SUBSCRIPTION_PATTERNS="CF优选-电信"
```

#### 启动服务

```bash
# 启用代理启动
python start_server.py

# 禁用代理启动（即使配置了代理）
python start_server.py --no-proxy
```

#### 传统代理配置（可选）

```bash
# 设置 Vless 代理（支持多个，用逗号、分号或换行分隔）
export VLESS_PROXIES="vless://uuid@host1:443?security=tls...,vless://uuid@host2:443?security=tls..."

# 或指定代理配置文件
export VLESS_PROXY_FILE="/path/to/proxy_config.txt"

# 同时支持普通 HTTP/HTTPS 代理
export HTTP_PROXY="http://proxy.example.com:8080"
export HTTPS_PROXY="http://proxy.example.com:8080"
```

#### Vless URI 格式

```
vless://{uuid}@{address}:{port}?{parameters}#{remark}
```

**参数说明：**

| 参数 | 说明 | 示例 |
|------|------|------|
| uuid | 用户 ID | 12345678-1234-1234-1234-123456789abc |
| address | 服务器地址 | example.com |
| port | 服务器端口 | 443 |
| security | 安全类型 | tls, reality, none |
| type | 传输类型 | tcp, ws, grpc |
| host | 主机名 | example.com |
| path | WebSocket 路径 | /ws |
| sni | TLS SNI | example.com |
| fp | 指纹 | chrome, firefox, safari |
| pbk | Reality 公钥 | PublicKey |
| sid | Reality ShortID | ShortID |

#### 代理池特性

- **自动轮换**：支持轮询和随机两种策略
- **健康检查**：自动检测代理可用性
- **故障转移**：自动切换到健康代理
- **多协议支持**：同时支持 Vless 和普通 HTTP 代理

### 订阅代理配置（推荐）

支持从订阅URL自动获取和筛选 Vless 节点。

#### 快速配置

```bash
# 运行配置脚本
python setup_proxy.py
```

#### 手动配置

创建 `.env` 文件：

```bash
# 订阅URL
VLESS_SUBSCRIPTION_URLS=https://example.com/subscription

# 节点匹配规则（如 CF优选-电信）
VLESS_SUBSCRIPTION_PATTERNS=CF优选-电信

# 启动时自动刷新
VLESS_AUTO_REFRESH_ON_START=true
```

#### 启动服务

```bash
# 使用代理启动脚本
python start_with_proxy.py
```

#### 代理管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/proxy/stats` | GET | 获取代理统计 |
| `/v1/proxy/nodes` | GET | 获取节点列表 |
| `/v1/proxy/refresh` | POST | 刷新订阅 |
| `/v1/proxy/test` | POST | 测试节点 |

详细配置说明请参考 [PROXY_SETUP.md](PROXY_SETUP.md)

## 🌐 代理功能详解

### 订阅管理

- **自动获取**：从订阅 URL 自动获取 Vless 节点
- **规则筛选**：按节点名称规则筛选（如 `CF优选-电信`）
- **本地存储**：将节点存储到本地文件，持久化管理

### 节点测试

- **并发测试**：同时测试多个节点的可用性
- **延迟测量**：测试节点响应时间
- **健康标记**：自动标记可用/不可用节点

### 代理管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/proxy/stats` | GET | 获取代理池统计信息 |
| `/v1/proxy/nodes` | GET | 获取节点列表 |
| `/v1/proxy/refresh` | POST | 刷新订阅并测试节点 |
| `/v1/proxy/test` | POST | 测试指定节点 |

### 使用示例

**刷新订阅**：
```bash
curl -X POST http://localhost:8000/v1/proxy/refresh \
  -H "Content-Type: application/json" \
  -d '{"test_nodes": true}'
```

**查看统计**：
```bash
curl http://localhost:8000/v1/proxy/stats
```

**获取节点**：
```bash
curl http://localhost:8000/v1/proxy/nodes
```

## 🎯 支持模型

| 模型 | 描述 |
|------|------|
| qwen3.6-plus | 最新旗舰模型 |
| qwen3.5-plus | 高性能模型 |
| qwen3.5-flash | 快速响应模型 |
| qwen3.5-max-2026-03-08 | 最大上下文模型（预览版） |
| qwen3-max | 最大参数模型 |
| qwen3-coder | 代码生成模型 |
| qwen2.5-max | 稳定版本模型 |

## 📁 项目结构

```
qwen-ai-reverse-api/
├── qwen_ai/              # Python SDK
│   ├── __init__.py
│   ├── adapter.py         # API 适配器
│   ├── client.py          # OpenAI 兼容客户端
│   ├── stream_handler.py  # 流处理
│   ├── tool_parser.py     # 工具解析
│   ├── vless_proxy.py     # Vless 代理池
│   ├── subscription.py    # 订阅管理
│   ├── node_storage.py    # 节点存储
│   ├── node_tester.py     # 节点测试
│   └── account_register.py # 账号注册模块
├── server.py              # FastAPI 服务
├── start_server.py        # 启动脚本
├── register_account.py    # 账号注册工具
├── get_jwt.py            # JWT 获取工具
├── requirements.txt       # 依赖
├── .env.example           # 环境变量示例
├── proxy_config.example.txt # 代理配置示例
├── PROXY_SETUP.md         # 代理配置文档
└── README.md              # 文档
```

## ⚠️ 免责声明

本项目是对 Qwen AI 网页版 API 的逆向工程，仅供学习研究使用。请遵守 Qwen AI 的服务条款，不要用于商业用途或大规模请求。

## 📄 License

[MIT License](LICENSE)