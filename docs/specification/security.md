# A2C-SMCP 安全性考虑

本文档描述实现 A2C-SMCP 协议时的安全性要求与建议。

## 传输安全

### TLS 要求

| 部署环境 | TLS 要求 |
|---------|---------|
| 公网部署 | **必须** 使用 TLS |
| 内网部署 | **推荐** 使用 TLS |
| 本地开发 | 可选 |

### TLS 配置建议

```python
# 推荐的 TLS 版本
TLS_VERSION = "TLSv1.2+"

# 推荐的密码套件
CIPHER_SUITES = [
    "TLS_AES_256_GCM_SHA384",
    "TLS_CHACHA20_POLY1305_SHA256",
    "TLS_AES_128_GCM_SHA256"
]
```

### mTLS（双向 TLS）

对于需要端到端保密的场景，**推荐**采用 mTLS：

- Client 和 Server 都需要证书
- 提供双向身份验证
- 适用于高安全要求的企业环境

## 认证与授权

### 认证机制

A2C-SMCP 通过 `AuthenticationProvider` 抽象认证：

```python
class AuthenticationProvider(ABC):
    @abstractmethod
    async def authenticate(
        self,
        server: AsyncServer,
        environ: dict,
        auth: dict | None,
        headers: dict
    ) -> bool:
        """验证连接请求"""
        pass
```

### 认证策略

| 策略 | 适用场景 | 安全级别 |
|------|---------|---------|
| API Key | 简单场景、内部服务 | 中 |
| JWT Token | 用户认证、有时效要求 | 高 |
| mTLS | 服务间通信、高安全要求 | 最高 |

### 默认认证实现

SDK 提供默认认证实现 `DefaultAuthenticationProvider`：

```python
auth = DefaultAuthenticationProvider(
    admin_secret="your_admin_secret",
    api_key_name="x-api-key"
)
```

**注意**: 默认实现仅适用于开发和测试，生产环境应实现自定义认证。

## 凭证管理

### 零凭证传播原则

A2C-SMCP 的核心安全原则是**零凭证传播**：

```
┌──────────────────────────────────────────────────┐
│                    Agent                          │
│                                                   │
│  ✗ 不持有敏感凭证                                 │
│  ✗ 不接触 MCP Server Token                       │
│  ✗ 不访问本地资源                                 │
└──────────────────────────────────────────────────┘
                        │
                        │ SMCP 协议
                        ▼
┌──────────────────────────────────────────────────┐
│                   Computer                        │
│                                                   │
│  ✓ 持有 MCP Server 凭证                          │
│  ✓ 管理本地资源访问                              │
│  ✓ 凭证不外传                                    │
└──────────────────────────────────────────────────┘
```

### 凭证存储建议

| 凭证类型 | 存储位置 | 加密要求 |
|---------|---------|---------|
| API Key | 环境变量 / 密钥管理服务 | 推荐 |
| 数据库密码 | 密钥管理服务 | 必须 |
| 证书私钥 | 文件系统（受保护）| 推荐 |

### 环境变量安全

```bash
# 推荐：使用环境变量
export API_KEY="your_api_key"

# 不推荐：硬编码
api_key = "your_api_key"  # 危险！
```

### MCP 上游授权（OAuth 2.0 等）

MCP 协议自身支持 OAuth 2.0 等授权机制以访问工具服务器的受保护资源。A2C-SMCP **不**在协议层介入该握手过程——这是"零凭证传播原则"在 MCP 集成上的直接推论。

#### 边界划分

```
┌───────────────┐        ┌───────────────┐        ┌──────────────────┐
│     Agent     │◀──────▶│   Computer    │◀──────▶│   MCP Server     │
│               │  SMCP  │               │  MCP   │  (受保护资源)     │
│ ✗ 不参与授权  │        │ ✓ 执行 OAuth  │        │                  │
│ ✗ 不持有 Token│        │ ✓ 存储 Token  │        │                  │
│               │        │ ✓ 负责刷新    │        │                  │
└───────────────┘        └───────────────┘        └──────────────────┘
```

#### Computer 实现要求

| 要求 | 说明 |
|------|------|
| **本地完成握手** | OAuth 流程（Authorization Code、Device Code 等）**必须**在 Computer 宿主环境内完成，不通过 A2C-SMCP 信道承载授权参数 |
| **凭证不外传** | Access Token、Refresh Token、`client_secret`、`code_verifier` 等**禁止**经由 A2C-SMCP 协议传输 |
| **用户引导本地化** | 需要用户完成浏览器授权或显示设备码时，**应**在 Computer 所在宿主环境呈现，不应通过 Agent 侧 UI 中转敏感 URL 参数 |
| **刷新透明** | Token 过期由 Computer 自动刷新；若刷新失败，返回 `4007 Tool Authorization Failed`（见 `error-handling.md`） |
| **授权缺失显式告知** | 工具首次调用前未完成授权时，返回 `4006 Tool Authorization Required`，不要泛化为一般工具执行错误 |

#### Agent 行为约束

- **禁止**在调用参数中尝试注入 Token、授权码或任何 OAuth 字段——这些字段即使被传输也不会被 Computer 信任。
- 收到 `4006/4007` 时，**不应**自动重试，应将 Computer 返回的 `auth_hint.message`（非敏感文案）透传给上层。
- 授权完成的判定由 Computer 负责；Agent **仅在用户显式重试**后再次发起 `client:tool_call`，不得基于启发式（如等待固定时间）自动重试。

#### 工具元数据提示（建议，非强制）

Computer 在向 Agent 暴露工具列表时，**建议**对需要授权的工具附加非敏感标注，便于 Agent 判断调用前置条件：

```python
{
    "name": "github_create_issue",
    "description": "...",
    "requires_auth": True,        # 建议字段
    "auth_provider": "github"     # 建议字段，仅用于展示，禁止包含 scope 之外的敏感细节
}
```

该字段在当前版本中**不是**协议强制字段，Agent **不应**依赖其存在；Computer SDK 可根据实现粒度自行决定是否暴露。后续版本会评估将其纳入 `tool` 数据结构。

## 房间隔离

### 隔离要求

Server **必须**实现以下隔离保障：

1. **跨房间访问禁止**: 事件不能路由到其他房间
2. **Agent 独占性**: 一个房间只能有一个 Agent
3. **消息隔离**: 通知只广播给同一房间成员

### 实现检查清单

```python
# Server 必须验证
def validate_room_access(sid, target_office_id):
    session = get_session(sid)
    if session.office_id != target_office_id:
        raise PermissionError("Cross-room access denied")
```

## 输入验证

### 数据验证要求

所有输入数据**必须**进行验证：

| 验证项 | 说明 |
|-------|------|
| 类型检查 | 确保字段类型正确 |
| 长度限制 | 防止缓冲区溢出 |
| 格式校验 | 验证 URL、ID 等格式 |
| 范围检查 | 验证数值在合理范围内 |

### 工具参数验证

```python
# 推荐：使用 Pydantic 进行验证
from pydantic import BaseModel, validator

class ToolCallParams(BaseModel):
    tool_name: str
    params: dict
    timeout: int

    @validator('timeout')
    def validate_timeout(cls, v):
        if v <= 0 or v > 3600:
            raise ValueError('Timeout must be between 1 and 3600')
        return v
```

## 资源限制

### DoS 防护

实现**应该**对以下资源设置限制：

| 资源 | 建议限制 |
|------|---------|
| 并发连接数 | 每 IP 100 个 |
| 请求频率 | 每秒 100 请求 |
| 消息大小 | 1MB |
| 工具调用超时 | 300 秒 |

### 限流实现

```python
# 示例：使用令牌桶算法
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=100, period=1)
def handle_request(request):
    # 处理请求
    pass
```

## 日志与审计

### 安全日志

**应该**记录以下安全相关事件：

| 事件类型 | 日志级别 |
|---------|---------|
| 认证失败 | WARNING |
| 跨房间访问尝试 | WARNING |
| 权限拒绝 | WARNING |
| 异常高频请求 | WARNING |
| 敏感操作 | INFO |

### 日志格式

```python
# 推荐的安全日志格式
logger.warning(
    "Authentication failed",
    extra={
        "client_ip": client_ip,
        "user_agent": user_agent,
        "reason": "Invalid API key",
        "timestamp": datetime.utcnow().isoformat()
    }
)
```

### 敏感信息过滤

日志**禁止**包含：

- API 密钥或 Token
- 密码
- 个人身份信息（PII）
- 信用卡号等金融信息

## 安全更新

### 依赖管理

- 定期更新依赖包
- 使用 `pip-audit` 或 `safety` 检查漏洞
- 订阅安全公告

### 漏洞响应

1. 评估漏洞影响
2. 制定修复计划
3. 发布安全补丁
4. 通知用户更新

## 安全检查清单

### 部署前检查

- [ ] TLS 已启用（公网部署）
- [ ] 认证机制已配置
- [ ] 敏感凭证未硬编码
- [ ] 输入验证已实现
- [ ] 资源限制已配置
- [ ] 安全日志已启用
- [ ] 依赖无已知漏洞

### 定期检查

- [ ] 证书有效性
- [ ] API 密钥轮换
- [ ] 日志审计
- [ ] 依赖更新
- [ ] 渗透测试

## 参考

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- Socket.IO 安全: https://socket.io/docs/v4/security/
- Python 安全: https://python-security.readthedocs.io/
