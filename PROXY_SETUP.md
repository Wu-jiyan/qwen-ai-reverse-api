# Vless 代理配置指南

## 快速开始

### 1. 配置环境变量

创建 `.env` 文件：

```bash
# 启用代理功能
ENABLE_PROXY=true

# 订阅URL
VLESS_SUBSCRIPTION_URLS="https://example.com/subscription"

# 节点匹配规则（如 CF优选-电信）
VLESS_SUBSCRIPTION_PATTERNS="CF优选-电信"

# 启动时自动刷新订阅
VLESS_AUTO_REFRESH_ON_START=true
```

### 2. 启动服务

```bash
# 启用代理启动
python start_server.py

# 禁用代理启动（即使配置了代理）
python start_server.py --no-proxy
```

### 3. 验证代理

```bash
# 查看代理统计
curl http://localhost:8000/v1/proxy/stats

# 查看节点列表
curl http://localhost:8000/v1/proxy/nodes

# 手动刷新订阅
curl -X POST http://localhost:8000/v1/proxy/refresh \
  -H "Content-Type: application/json" \
  -d '{"test_nodes": true}'
```

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ENABLE_PROXY` | 是否启用代理功能 | `false` |
| `VLESS_SUBSCRIPTION_URLS` | 订阅URL（支持多个，逗号分隔） | - |
| `VLESS_SUBSCRIPTION_PATTERNS` | 节点匹配规则 | `CF优选-电信` |
| `VLESS_AUTO_REFRESH_ON_START` | 启动时自动刷新订阅 | `true` |
| `VLESS_STORAGE_FILE` | 节点存储文件 | `vless_nodes.json` |

### 节点匹配规则

支持正则表达式匹配节点名称：

```bash
# 匹配特定运营商
VLESS_SUBSCRIPTION_PATTERNS="CF优选-电信"

# 匹配多个规则（逗号分隔）
VLESS_SUBSCRIPTION_PATTERNS="CF优选-电信, CF优选-移动, 美国"

# 使用正则表达式
VLESS_SUBSCRIPTION_PATTERNS=".*香港.*"
```

## 代理管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/proxy/stats` | GET | 获取代理统计 |
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

**测试节点**：
```bash
curl -X POST http://localhost:8000/v1/proxy/test \
  -H "Content-Type: application/json" \
  -d '{"pattern": "CF优选-电信", "timeout": 10}'
```

## 工作原理

1. **订阅获取**：从配置的订阅URL获取Base64编码的节点列表
2. **节点筛选**：按规则筛选符合条件的节点
3. **健康测试**：并发测试节点可用性和延迟
4. **本地存储**：将可用节点存储到本地JSON文件
5. **随机使用**：API调用时随机选择可用节点

## 故障排除

### 代理未启用

检查 `.env` 文件：
```bash
ENABLE_PROXY=true
```

### 订阅获取失败

检查订阅URL：
```bash
curl -s "https://your-subscription-url" | base64 -d
```

### 节点测试失败

检查网络连接和节点可用性：
```bash
curl -X POST http://localhost:8000/v1/proxy/test \
  -H "Content-Type: application/json" \
  -d '{"timeout": 30}'
```
