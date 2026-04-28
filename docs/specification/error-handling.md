# A2C-SMCP 错误处理规范

> **状态**: 草案
>
> 本章节目前为草案状态，具体错误码与结构仍在演进中。

## 概述

A2C-SMCP 协议定义了统一的错误处理机制，确保 Agent、Server、Computer 之间能够正确传递和处理错误信息。

## 错误码定义

### 通用错误码

| 代码 | 名称 | 含义 | 典型触发场景 |
|------|------|------|-------------|
| 400 | Bad Request | 无效请求格式 | 数据结构校验失败、字段缺失或类型错误 |
| 401 | Unauthorized | 未授权 | 认证失败、Token 无效 |
| 403 | Forbidden | 权限违规 | 跨房间访问、Agent 独占冲突、未授权操作 |
| 404 | Not Found | 资源不存在 | 工具或 Computer 不存在、MCP 配置缺失 |
| 408 | Timeout | 请求超时 | 工具调用超过约定超时时间未返回 |
| 500 | Internal Error | 内部错误 | Server 或 Computer 端逻辑异常 |

### 工具调用错误码

| 代码 | 名称 | 含义 |
|------|------|------|
| 4001 | Tool Not Found | `tool_name` 在指定 MCP Server 中不存在；**不**含 `mcp_server` 本身缺失场景（用 [4014](#mcp-server-not-found4014)）|
| 4002 | Tool Disabled | 工具被禁用 |
| 4003 | Tool Execution Failed | 工具执行失败 |
| 4004 | Tool Timeout | 工具执行超时 |
| 4005 | Tool Requires Confirmation | 工具需要二次确认 |
| 4006 | Tool Authorization Required | 工具需要 MCP 上游授权（如 OAuth 2.0），Computer 当前无有效凭证或尚未完成授权（见下方[4006/4007 判定决策表](#40064007-判定决策表)）|
| 4007 | Tool Authorization Failed | MCP 上游授权流程失败、Token 已失效、刷新失败、或权限不足（见下方[4006/4007 判定决策表](#40064007-判定决策表)）|

### DPE 错误码

| 代码 | 名称 | 含义 |
|------|------|------|
| 4011 | DPE Resolver Not Configured | Computer 未注册 DPE Resolver hook，无法处理 `client:get_dpe`（见 [`dpe.md` Resolver 章节](dpe.md#dpe-resolver-hook业务层)）|
| 4012 | Invalid DPE URI | Agent SDK 构造层硬错误——URI 不符合 `dpe://` scheme 规范（缺 host、缺 doc-ref、scheme 错等）。**含 query/fragment 在 Computer 解析层容错丢弃 + WARN，不报此码**（详见 [F4 分层处理](dpe.md#uri-query--fragment-处理分层)）|
| 4013 | DPE Resolution Failed | Resolver / 上游 / mimetype 失败——payload 内 `category` 字段细分（见 [§DPE 解析失败](#dpe-解析失败4013)）|

### MCP Server 路由错误码

| 代码 | 名称 | 含义 |
|------|------|------|
| 4014 | MCP Server Not Found | 引用的 `mcp_server` 名字未注册（见 [§MCP Server Not Found](#mcp-server-not-found4014)）|
| 4015 | MCP Capability Not Supported | MCP Server 已注册但未声明所需 capability（见 [§MCP Capability Not Supported](#mcp-capability-not-supported4015)）|

### 连接与房间管理错误码

| 代码 | 名称 | 含义 |
|------|------|------|
| 4008 | Protocol Version Mismatch | HTTP 握手阶段，URL query 中的 `a2c_version` 与 Server 不兼容 |
| 4101 | Room Full | 房间已有 Agent |
| 4102 | Room Not Found | 房间不存在 |
| 4103 | Not In Room | 未加入房间 |
| 4104 | Cross Room Access | 跨房间访问被拒绝 |

### Finder 文档系统错误码

| 代码 | 名称 | 含义 |
|------|------|------|
| 4201 | Document Not Found | 文档引用（`doc_ref`）不存在 |
| 4202 | Page Out of Range | 页码超出文档的 `page_count` 范围 |
| 4203 | Element Not Found | 元素 ID 不存在 |
| 4204 | Invalid DPE URI | `dpe://` URI 格式错误或校验失败 |

## 错误响应格式

A2C-SMCP 协议级错误（HTTP 握手层 + Socket.IO ack 层）统一采用**扁平 ErrorPayload** shape：标准字段 `code` / `message` 顶层平铺，code-specific 字段（如 `category` / `mcp_server_name` / `uri`）顶层并列，诊断信息封装在 `details` 子对象内。

!!! warning "无嵌套 envelope"

    协议**不使用** `{"error": {"code": ..., "message": ...}}` 形式的嵌套包装。SDK 反序列化时直接读取顶层字段，**禁止**二次 unwrap。

> **作用域**：本节定义 `4008` / `4011-4015` 这类协议事件级错误的响应 shape。**不**适用：(a) `server:join_office` 等返回 `(success, error_msg)` 元组的事件，见 [§事件级错误处理](#事件级错误处理)；(b) `client:tool_call` 工具失败，使用 MCP `CallToolResult.isError=true`，见 [§错误传播](#错误传播)。

### Flat ErrorPayload schema

```python
class ErrorPayload(TypedDict, total=False):
    code: int                       # 必选：错误码
    message: str                    # 必选：人类可读描述
    details: NotRequired[dict]      # 可选：诊断容器，仅供日志 / 调试
    # 各错误码可附加 code-specific 顶层字段，详见下方总表
```

### 传输分层

| 层 | 错误码 | 承载方式 |
|----|--------|----------|
| HTTP 握手层 | `4008` | HTTP 400 响应 body（JSON）+ `X-A2C-Error-Code` header（冗余诊断）|
| Socket.IO ack 层 | `4011` / `4012` / `4013` / `4014` / `4015` | ack callback 第一参（dict）|

两层使用**同一种** flat shape，差别仅在传输通道。

### 各错误码标准字段总表

除 `code` / `message` 外的顶层 code-specific 字段，以及 `details` 内推荐 key：

| code | 顶层 code-specific 字段 | `details` 内推荐 key |
|------|------------------------|---------------------|
| `4008` | `server_version` / `client_version` / `min_supported` / `max_supported` | — |
| `4011` | `uri` | — |
| `4012` | `uri` / `reason` | — |
| `4013` | `category` / `uri` | `mcp_server_name` / `mcp_error` / `resolver_exception`（按 [`category` 分流](#dpe-解析失败4013)）|
| `4014` | `mcp_server_name` | — |
| `4015` | `mcp_server_name` / `capability` | — |

各错误码完整 payload 示例与触发时机详见对应章节（[§4008](#协议版本不匹配4008) / [§DPE 资源访问错误](#dpe-资源访问错误) / [§4014](#mcp-server-not-found4014) / [§4015](#mcp-capability-not-supported4015)）。

### `details` 字段约束（协议级）

`details` 是**诊断信息容器**，承载日志 / 调试上下文。协议级约束：

- Agent **MUST NOT** 把 `details` 内容透传给最终用户——避免泄露内部实现细节
- 协议级标准 key 见上表；新增 standard key 算 minor 升级
- 业务自定义 key 可附加，**不进入**协议演进语义（不算 breaking）

#### `details` 内禁止包含的敏感信息

- API 密钥或 Token
- 内部 IP 地址或端口
- 数据库连接信息
- 用户密码或凭证
- 堆栈跟踪（生产环境）

### SDK 反序列化建议

按 `code` 分发到 code-specific TypedDict 解析，**不要**写 over-generic `details: dict` 把所有顶层字段折叠收集——会丢失类型信息与 IDE 推导能力。

> **注**：协议规范仅提供 Python reference impl。其他 SDK 由各自实现决定具体解析模式——A2C-SMCP 协议文档不堆砌多语言示例。

## 事件级错误处理

### server:join_office 响应

```python
# 成功
(True, None)

# 失败
(False, "Room already has an agent")
```

### client:tool_call 响应

工具调用使用 MCP 的 `CallToolResult` 结构返回结果：

```python
class CallToolResult:
    content: list[TextContent | ImageContent | EmbeddedResource]
    isError: bool  # 是否为错误结果
    meta: dict     # 元数据
```

当 `isError=True` 时，`content` 中包含错误信息。

## 超时处理

### Agent 端超时

Agent 在发起工具调用时指定 `timeout`：

```python
result = await agent.emit_tool_call(
    computer="my-computer",
    tool_name="slow_tool",
    params={},
    timeout=30  # 30 秒超时
)
```

超时后，Agent 应：

1. 发送 `server:tool_call_cancel` 取消请求
2. 返回超时错误给调用方

```python
# 超时返回示例
CallToolResult(
    content=[TextContent(text="Tool call timeout")],
    isError=True,
    meta={"timeout": True}
)
```

### Server 端超时

Server 在转发请求时应设置合理的超时：

- 使用 Agent 请求中的 `timeout` 值
- 添加少量缓冲时间（如 5 秒）

### Computer 端超时

Computer 应在工具执行超时时：

1. 尝试中断工具执行
2. 返回超时错误

## 重试策略

### 建议的重试策略

| 错误类型 | 是否重试 | 策略 |
|---------|---------|------|
| 400 Bad Request | 否 | 修复请求后重试 |
| 401 Unauthorized | 否 | 重新认证后重试 |
| 403 Forbidden | 否 | 不重试 |
| 404 Not Found | 否 | 不重试 |
| 408 Timeout | 可选 | 指数退避重试 |
| 500 Internal Error | 可选 | 指数退避重试 |

### 指数退避示例

```python
async def retry_with_backoff(func, max_retries=3):
    for i in range(max_retries):
        try:
            return await func()
        except TimeoutError:
            if i == max_retries - 1:
                raise
            wait_time = (2 ** i) + random.uniform(0, 1)
            await asyncio.sleep(wait_time)
```

## 错误传播

### 工具调用错误传播链

```
MCP Server → Computer → Server → Agent
     │           │          │        │
     └───────────┴──────────┴────────┘
                错误信息保留
```

每一层应：

1. 记录错误日志
2. 将错误信息向上传播
3. 不丢失原始错误细节

### 日志记录建议

```python
# 推荐的日志格式
logger.error(
    "Tool call failed",
    extra={
        "req_id": req_id,
        "tool_name": tool_name,
        "computer": computer,
        "error_code": error.code,
        "error_message": error.message
    }
)
```

## 协议版本不匹配（4008）

**触发时机**：客户端（Agent / Computer）通过 Socket.IO 连接 Server，**HTTP 中间件层**校验 URL query 中的 `a2c_version` 发现与 Server 不兼容。校验发生在 Socket.IO 处理之前，业务代码无法影响。

### 4008 是 HTTP body code，不是 WS close code

!!! warning "明确语义边界"

    **4008 是 ErrorPayload.code 字段值，承载于 HTTP 400 响应 body 中**。
    4008 **不是** WebSocket close code（RFC 6455 自定义码段 4xxx）——协议版本校验在 HTTP 层完成，发生在 WS 帧建立之前，不存在 WS close 形态。
    SDK 实现 **MUST NOT** 把 4008 与 WS close code 4xxx 混淆。

### HTTP 响应规范

```
HTTP/1.1 400 Bad Request
Content-Type: application/json
X-A2C-Error-Code: 4008

{
  "code": 4008,
  "message": "Protocol version mismatch",
  "server_version": "0.2.0",
  "client_version": "0.1.5",
  "min_supported": "0.2.0",
  "max_supported": "0.2.999"
}
```

`X-A2C-Error-Code` 响应 header 是冗余诊断辅助：当客户端无法访问 body 时（罕见 transport 边角情况），可从 header 中识别错误类型。**不替代** body，body 是 single source of truth。

### 字段说明

| 字段 | 必需 | 说明 |
|------|------|------|
| `code` | 是 | 固定 `4008` |
| `message` | 是 | 人类可读的错误信息 |
| `server_version` | 是 | Server 当前支持的协议版本（Client 据此决定是否升级） |
| `client_version` | 是 | Server 从 URL query 读取的客户端版本（回显供诊断） |
| `min_supported` | 是 | Server 支持的最低协议版本 |
| `max_supported` | 是 | Server 支持的最高协议版本 |

### SDK 实现要求

- Client SDK **必须**解析 HTTP 400 的响应 body，识别 `code: 4008`，转化为专属异常（如 `ProtocolVersionError`），**禁止**静默重试
- 异常信息应明确告知用户两边版本，便于快速判断应升级哪端
- 客户端 transport 顺序 **SHOULD** 配置为 `polling → websocket`（绝大多数 socketio 客户端默认即如此），保证首个握手请求是 HTTP polling，body 可访问
- 可选：SDK 在本地日志中打印诊断信息（当前 SDK 声称的 PROTOCOL_VERSION 常量、接收到的 server_version）

### Python 解析示例（reference impl）

```python
import json
import socketio
from a2c_smcp import PROTOCOL_VERSION
from a2c_smcp.exceptions import ProtocolVersionError

sio = socketio.AsyncClient()
try:
    await sio.connect(
        f"wss://server.example.com?a2c_version={PROTOCOL_VERSION}",
        auth={"role": "agent", "agent_id": "..."},
    )
except socketio.exceptions.ConnectionError as e:
    # python-socketio 在 HTTP 非 2xx 时把 body 放进异常 message
    raw = str(e)
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        raise  # 非协议级错误，保持原异常
    if body.get("code") == 4008:
        raise ProtocolVersionError(
            client_version=body.get("client_version"),
            server_version=body.get("server_version"),
            min_supported=body.get("min_supported"),
            max_supported=body.get("max_supported"),
        )
    raise
```

> **注**：协议规范仅提供 Python reference impl。其他 SDK（Rust / TypeScript / Go 等）的具体解析模式由各 SDK 自行决定——A2C-SMCP 协议文档不堆砌多语言示例。

详细的版本语义、兼容性规则与握手流程见 [协议版本与握手](versioning.md)。

---

## MCP 上游授权错误响应

MCP 协议自身定义了工具服务器的 OAuth 2.0 授权流程。A2C-SMCP 不介入该握手过程；本章仅定义**授权结果如何向 Agent 反馈**，使 Agent 能够区分"工具坏了"与"工具需要用户授权"。

> **完整的安全边界、Computer 实现要求与 Agent 行为约束，见 [`security.md` → MCP 上游授权（OAuth 2.0 等）](security.md#mcp-上游授权oauth-20-等)。** 本章仅承载**响应结构与错误码**，行为层约束以 `security.md` 为准，避免重复维护。

### 授权失败的响应结构

当 Computer 调用 MCP 工具因上游授权问题失败时，使用 `CallToolResult` 返回错误，并在 `meta` 中携带结构化提示：

```python
CallToolResult(
    content=[TextContent(text="此工具需要授权 GitHub 账号后方可使用")],
    isError=True,
    meta={
        "error_code": 4006,  # 或 4007
        "mcp_server": "github-mcp",
        "auth_hint": {
            # 可选：引导用户完成授权的提示信息
            "action": "user_authorization_required",
            "message": "请在 Computer 宿主环境完成 GitHub OAuth 登录后重试"
        }
    }
)
```

### 4006/4007 判定决策表

为消除"未授权 vs 授权失败"的边界歧义，Computer **MUST** 按下表把上游 MCP Server / OAuth Provider 的具体表现映射到协议错误码：

| 上游表现 | 错误码 | 语义 |
|---|---|---|
| Computer 从未为该 MCP Server 配置授权（无 token / 无 client credentials）| **4006** | 用户**首次**授权 |
| 上游返回 HTTP 401 Unauthorized（凭证缺失、非法、未提供）| **4006** | 用户**重新**授权 |
| 上游返回 HTTP 403 Forbidden（已登录但权限/scope 不足）| **4007** | 已授权但能力不足，用户调整 scope 或换账号 |
| Token 过期 + 刷新失败（refresh_token 无效 / 被撤销）| **4007** | 历史授权失效，用户需重新走 OAuth 流程 |
| 用户已主动 revoke OAuth 授权 | **4007** | 历史授权已被撤销 |
| 凭证存在但 scope 不足（上游未明确返回 401/403，但断言权限不够）| **4007** | 同 403 类，归"已授权但失败" |
| OAuth provider 自身故障（5xx / 网络）| **4003 Tool Execution Failed** | 不属于授权语义，按通用工具失败处理 |

**简明判别**：

- 区分点是"**用户是否曾经授权**"——`4006` = 没授权过 / 凭证不存在；`4007` = 曾授权但当前不可用
- 当 Computer 无法可靠判别时，倾向于报 `4006`（提示用户重新走授权流程是稳妥兜底）

**Agent 行为差异**：Agent 收到 `4006` 应引导用户**首次/重新**完成授权；收到 `4007` 应引导用户**检查权限设置或重新授权**——区别仅在 UX 文案，机器路由可统一。

### 字段说明

| 字段 | 强度 | 说明 |
|------|------|------|
| `meta.error_code` | **MUST** | `4006`（未授权）或 `4007`（授权失效），按上方[判定决策表](#40064007-判定决策表)映射 |
| `meta.mcp_server` | **MUST** | 触发授权错误的 MCP Server 标识，便于 Agent 定位 |
| `meta.auth_hint` | **SHOULD** | 面向用户的非敏感提示对象。Computer **SHOULD** 提供以协助 Agent/Host 引导用户；缺失时 Agent 仍能基于 `error_code` 做兜底处理 |
| `meta.auth_hint.action` | MAY | 机器可读动作标识（如 `user_authorization_required` / `token_refresh_required`），便于 Host 路由到不同 UI |
| `meta.auth_hint.message` | **SHOULD** | 用户可读的一句话引导（如"请在 Computer 宿主环境完成 GitHub OAuth 登录后重试"）；强烈建议提供以满足最小可用 UX |

#### auth_hint 安全边界

`auth_hint` 是协议层**唯一**面向 Agent 暴露的授权相关字段。为防止凭证经此通道泄漏给 Agent，Computer **MUST NOT** 在 `auth_hint`（任何子字段）中包含以下任何一类内容：

| 类别 | 禁止字段示例 |
|---|---|
| 访问凭证 | `access_token` / `refresh_token` / `id_token` / `bearer_token` / 任何形式的 Token |
| OAuth 流程参数 | `code` / `code_verifier` / `code_challenge` / `state` / `nonce` |
| 客户端凭证 | `client_id` / `client_secret` / `assertion` / `client_assertion` |
| 完整授权 URL | 任何包含上述 query 参数的完整 URL（即使已经 url-encode 也禁止） |
| 用户敏感数据 | 用户密码、TOTP/OTP、安全问题答案 |

允许包含：

- 自然语言描述（"需要登录 GitHub 后重试"）
- MCP Server 名称、工具名称
- 不含敏感参数的着陆页 URL（如 `https://example.com/login`，无 query）

> 完整凭证传播禁令见 [`security.md` → 零凭证传播原则](security.md#零凭证传播原则)。`auth_hint` 是该原则下的**唯一豁免**——豁免范围严格限于上表"允许包含"部分。

## DPE 资源访问错误

### DPE Resolver 未配置（4011）

**触发时机**：Agent 调用 `client:get_dpe`，Computer 检查发现未注册 DPE Resolver hook。

**响应结构**（Socket.IO ack 数据）:

```json
{
  "code": 4011,
  "message": "DPE Resolver Not Configured",
  "uri": "dpe://com.example.docs/rpt-2026"
}
```

**说明**：

- A2C 协议**不允许**在未注册 Resolver 时降级到 inline 透传 ResourceContents——这是设计意图（避免 Socket.IO 承载大体量 DPE 内容）
- Computer 业务方**MUST**在启动时显式注册 Resolver（见 [DPE Resolver Hook](dpe.md#dpe-resolver-hook业务层)）
- 业务实现自由度高：上传对象存储 / 落本地缓存 / 任意 URI scheme 都可

### 无效 DPE URI（4012）

**触发时机**：Agent SDK **构造层** URI 校验失败（硬错误）。Computer **解析层**对 query / fragment 容错丢弃 + WARN，**不报此码**——分层规则详见 [URI query / fragment 处理分层](dpe.md#uri-query--fragment-处理分层)。

**响应结构**（Socket.IO ack 数据）:

```json
{
  "code": 4012,
  "message": "Invalid DPE URI",
  "uri": "dpe://host",
  "reason": "missing doc-ref"
}
```

**常见违规**（Agent SDK 构造层 / Computer 严重格式错误）：

- scheme 不是 `dpe`
- `host` 为空 / 不符合 [反向域名命名规范](dpe.md#host-命名规范)
- `doc-ref` 缺失或为空（如 `dpe://host` / `dpe://host/` 形式）

**注意**：携带 query 参数或 fragment 的 URI 在 Agent SDK 构造层报 4012；但 Computer 解析层遇到这类 URI 会**容错丢弃 + WARN**，不报 4012（健壮性优先）。

### DPE 解析失败（4013）

**触发时机**：Computer 在处理 `client:get_dpe` 流程中遇到非构造类失败（Resolver / 上游 / mimetype）。

**响应结构**（Socket.IO ack 数据）:

```json
{
  "code": 4013,
  "message": "DPE Resolution Failed",
  "category": "upstream_unavailable",
  "uri": "dpe://com.example.docs/rpt-2026",
  "details": {
    "mcp_server_name": "com.example.docs",
    "mcp_error": "connection timeout"
  }
}
```

#### `category` 字段（SHOULD 携带）

`category` 是 4013 的细分维度（v0.2 锁定 4 个枚举值）。SDK 收到无 `category` 的 4013 时按 generic 处理（向前兼容）。

| `category` | 触发场景 | Agent UX 建议 |
|------------|----------|---------------|
| `upstream_unavailable` | MCP Server 不可用 / `resources/read` 超时 / 上游 5xx | 提示"DPE 来源暂时不可用"，**可重试** |
| `invalid_dpe_mime` | DPE 内容形态不规范：mimetype 非 `application/vnd.a2c.dpe-inline+json` / `application/vnd.a2c.dpe-uri+json`，**或** mimetype 合法但 body 解析失败 / schema 不合法 | 提示"DPE 来源实现不规范"，**不要重试** |
| `resolver_error` | Resolver Hook 抛异常（业务上传失败、IO 错误、外部存储签名失败）| 提示业务层故障，**不要重试** |
| `resolver_returned_invalid` | Resolver 返回的 `A2CResource` 缺 `uri` / 字段非法 | 提示业务层 bug，**不要重试** |

#### `details` 字段（可选）

`details` 承载 category-specific 上下文（仅供日志 / 调试）：

| 字段 | 适用 category | 说明 |
|------|---------------|------|
| `mcp_server_name` | 全部 | 定位上游 server |
| `mcp_error` | `upstream_unavailable` / `invalid_dpe_mime` | 透传上游错误描述 |
| `resolver_exception` | `resolver_error` / `resolver_returned_invalid` | Resolver 异常类名 / 消息 |

Agent **MUST NOT** 把 `details` 透传给最终用户——避免泄露内部信息。

#### 演进规则

- 新增 `category` 值 → **不算 breaking**（minor 升级即可）；SDK **MUST** 把未知 category 当作 generic 处理
- 删除 / 重命名 `category` 值 → 算 breaking（需 MAJOR）
- **不允许**业务自定义 `category`——保持枚举为协议级封闭集合（业务自定义错误请用 4013 + `details` 或专用业务码段）

Agent 行为建议：根据 `category` 决定是否重试 / 提示用户 / 报告运维。

### MCP Server Not Found（4014）

**触发时机**：客户端事件（`client:get_resources` / `client:tool_call` / `client:get_dpe` 等）引用的 `mcp_server` 名字在 Computer 上未注册。对 `client:get_dpe`，特指 dpe URI 中的 `host` 反查不到对应 MCP Server。

**响应结构**（Socket.IO ack 数据）:

```json
{
  "code": 4014,
  "message": "MCP Server not registered",
  "mcp_server_name": "com.example.docs"
}
```

**字段说明**：

| 字段 | 必需 | 说明 |
|------|------|------|
| `code` | 是 | 固定 `4014` |
| `message` | 是 | 人类可读 |
| `mcp_server_name` | 是 | 客户端引用的 server 名（或 dpe URI 的 host）|

**Agent 行为建议**：刷新 server list（调用 `client:get_config`）后重试；持续不存在则提示用户 server 已下线。

### MCP Capability Not Supported（4015）

**触发时机**：MCP Server 已注册，但未声明所请求事件依赖的 capability。例如 `client:get_resources` 调用时该 server 未声明 `resources` capability。

**响应结构**（Socket.IO ack 数据）:

```json
{
  "code": 4015,
  "message": "MCP Server does not support 'resources' capability",
  "mcp_server_name": "com.example.docs",
  "capability": "resources"
}
```

**字段说明**：

| 字段 | 必需 | 说明 |
|------|------|------|
| `code` | 是 | 固定 `4015` |
| `message` | 是 | 人类可读 |
| `mcp_server_name` | 是 | 目标 server |
| `capability` | 是 | 缺失的 capability 名（`resources` / `tools` / `prompts` 等 MCP 标准 capability）|

**Agent 行为建议**：跳过此 server，不再向其发送同类事件；可在 server list UI 中标注能力缺失。

## TODO

> 以下功能尚未实现，计划在后续版本中完善：

- [ ] 统一的错误码定义文件
- [ ] 错误码国际化支持
- [ ] 错误追踪 ID（trace_id）
- [ ] 错误统计和监控接口
- [ ] 工具元数据层面的 `requires_auth` 标注（见 `security.md`）

## 参考

- MCP CallToolResult: https://github.com/modelcontextprotocol/specification
- Socket.IO 错误处理: https://socket.io/docs/v4/handling-errors/
