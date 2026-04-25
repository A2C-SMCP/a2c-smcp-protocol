# 协议版本与握手

**当前协议版本**: `0.2.0`

A2C-SMCP 作为三方参与（Agent / Server / Computer）的协议，必须保证同一房间内的成员以兼容的协议版本通信。本规范定义协议版本号语义、兼容性判定规则，以及在 **Socket.IO 连接的 HTTP 层**完成的版本校验流程。

---

## 设计取向

A2C-SMCP 借鉴 Socket.IO 自身对 `EIO` 版本号的处理方式：**把协议版本放在最底层、业务代码之前的传输层**，确保校验行为与任何业务逻辑解耦。

- 每个运行中的 Server 实例在某一时刻**仅支持一个协议版本**（由 Server 实现者通过部署决定）
- 客户端（Agent / Computer）在 Socket.IO 连接时通过 **URL query 参数** 声明协议版本
- Server 在 **HTTP 中间件层**（Socket.IO 处理之前）完成校验；不兼容时返回 HTTP 400 拒绝连接
- 这带来**传递性保证**：同一房间内的 Agent 与 Computer 必然兼容，**不需要** peer-level 的二次校验

需要多版本共存的部署场景（如灰度发布、分阶段迁移）通过**部署拓扑**（多 Server 实例、DNS 分流、负载均衡）实现，而非侵入协议。

### 为什么不放在 `auth` 对象里

`auth` 对象是 Socket.IO 为**应用层身份认证**提供的入口（如 token、用户标识）。将协议版本放入 `auth` 有三个问题：

1. **类别混淆**：版本是"能不能说同一种话"（协议层），认证是"你是谁"（业务层），二者不应共用一个 envelope
2. **可被业务代码破坏**：`auth` 的处理发生在用户编写的 `connect` handler 中；handler 异常、中间件拦截、auth 字段被改写等情况都可能让版本校验失效
3. **与未来演进冲突**：生产环境常把 token 迁移到 HTTP header；一旦 `auth` 成为边缘路径，版本校验不应受影响

因此协议版本放在 **URL query string** 中，校验在 HTTP 层完成；身份相关字段（如 `role`）留在 `auth` 对象。

---

## 协议依赖与最低 SDK 版本

A2C-SMCP 协议在 v0.2 起把元数据下沉到 MCP 标准字段（`Resource.annotations.priority` / `Resource.annotations.audience` / `Resource.annotations.lastModified` / `Resource._meta`）。SDK 实现方在升级到 v0.2 时，必须确保所用的底层 MCP SDK 已**完整支持**上述字段——否则 `resources/list` 序列化/反序列化会丢失 A2C 元数据，导致 Computer 端 Desktop / Finder 组织错乱。

### 锚定的 MCP 规范版本

| 协议版本 | 锚定的 MCP 规范修订版 | 链接 |
|---|---|---|
| **v0.2.0** | **MCP 2025-06-18 修订版**（含 `annotations.priority` / `audience` / `lastModified` / `_meta`） | [MCP Server Resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources#annotations) |

A2C-SMCP v0.2 的元数据语义以**该 MCP 规范修订版**为权威依据。MCP SDK 实现若使用更旧的修订版（如 2024-11-05）可能缺失上述字段，导致与 A2C 协议不兼容。

### 最低 MCP SDK 版本

| 协议版本 | Python `mcp` 包 | Rust `rmcp` crate | 必需字段可用性 |
|---|---|---|---|
| **v0.2.0** | `mcp >= 1.15.0` | `rmcp >= 0.11.0` | `Resource.annotations.priority` / `audience` / `lastModified` / `Resource._meta` 均原生可用 |
| v0.1.x | `mcp >= 1.0.0` | — | 仅依赖 `Resource.uri` / `Resource.name` / `Resource.description`；元数据走 URI query |

!!! note "为什么 Rust 锚定 `rmcp >= 0.11.0` 而非更新的 1.x"

    `rmcp 0.11.0` 是 rust-sdk 当前生产版本，已验证完整支持上述字段。锚定在 `0.11.0` 而非 `1.5.0+` 的考量：避免把"v0.2 协议升级"与"rmcp 1.x 大版本迁移"两个独立工程耦合，降低 rust-sdk 升级风险。rust-sdk 后续可独立评估升级到 rmcp 1.x，作为 v0.2.x SDK PATCH 内的实现优化（符合 [SDK PATCH 自由原则](#sdk-仓库)）。

SDK 实现方在 `pyproject.toml` / `Cargo.toml` 声明依赖时**MUST**满足上述最低版本。低于该版本时，SDK 的 `Resource` 类型可能缺失上述字段，导致 v0.2 协议字段被静默丢弃。

如所选 MCP SDK 在 SDK 实现方目标语言生态中尚未支持上述字段，可考虑：(a) 等待 SDK 升级；(b) fork 维护私有补丁；(c) 自定义序列化层兜底——但**不建议**为这一兼容性裂缝向 A2C 协议要求降级（A2C 严格锚定 MCP 标准是设计取向）。

### 校验建议

SDK 启动时可执行一次轻量自检：

```python
from mcp.types import Resource, Annotations

# 自检：v0.2 协议要求的字段是否可用
assert hasattr(Annotations, "priority"), \
    "底层 mcp SDK 版本过低，缺失 Annotations.priority；请升级到 mcp>=1.15.0"
```

若自检失败，应在启动阶段 fail-fast 而非运行期才暴露。

---

## 版本号语义（MAJOR.MINOR.PATCH）

A2C-SMCP 协议版本号采用**语义化版本（Semantic Versioning）**，格式为 `MAJOR.MINOR.PATCH`。每一位的含义与兼容性约束如下：

### MAJOR

**触发条件**（任一即 MAJOR bump）：

- 移除或重命名已有事件（如将 `client:get_tools` 改名为 `client:list_tools` 之类）
- 移除已有事件的**必需**字段
- 改变已有字段的**语义**（如 `priority` 从 int [0,100] 变为 float [0,1]）
- 改变已有字段的**类型**（如 `list[str]` 改为 `dict`）
- 移除或改变已有错误码
- 改变事件的**路由语义**（如 `client:*` 前缀的含义）
- 删除或重命名 URI scheme（`window://` / `dpe://`）、或改变 URI 语法

**兼容性**：

- 不同 MAJOR **完全不兼容**
- 示例：`1.5.2` 与 `2.0.0` 无法互通

### MINOR

**触发条件**（任一即 MINOR bump）：

- 新增事件（新的 `client:*` / `server:*` / `notify:*`）
- 新增事件**可选**字段（`NotRequired[...]`）
- 新增错误码
- 新增 URI scheme 或新的路径模式
- 新增非强制的 MCP Server 声明要求（如推荐但不强制的 `_meta` 字段）

**兼容性**（见下方"兼容性判定规则"）：

- 同 MAJOR 内，v1.0+ 向后兼容（较新的 MINOR 能接纳较旧 MINOR 的客户端）
- v0.x 阶段 MINOR 必须严格一致

### PATCH

**触发条件**：

- Bug 修复（不改变协议语义）
- 文档澄清（不改变行为）
- 错误信息文案优化
- 性能/稳定性改进（对外行为不变）

**强约束（wire format 兼容性）**：

PATCH 升级 **MUST** 保持 wire format **完全字节兼容**——

| 严禁项 |
|---|
| 新增 / 删除 / 重命名任何字段（即使是可选字段）|
| 修改字段类型、值域、必需性 |
| 修改事件名、错误码取值或含义 |
| 修改默认值 |

PATCH 仅允许：实现 bug 修复、错误信息文案打磨、文档勘误、内部实现优化、性能改进。任何会让序列化输出/输入字节序列发生变化的改动**MUST**走 MINOR bump（v0.x 阶段也即破坏性升级）。

**兼容性**：

- 同 MAJOR.MINOR 内 PATCH **永远兼容**（互发任意 PATCH 报文必定能解析）
- 示例：`0.2.0` 与 `0.2.3` 无需协商即可互通，且双方序列化输出可互相解析

---

## 兼容性判定规则

### v0.x（MAJOR = 0，不稳定阶段）

SemVer 规范中 `0.x.y` 视为公开 API 不稳定。A2C-SMCP 在 v0.x 阶段**任何 MINOR 都可能是破坏性变更**（例如 0.1 → 0.2 的 URI 重构）。因此：

- **MAJOR.MINOR 必须严格匹配**（如 `0.2.0` 仅兼容 `0.2.x`）
- PATCH 可自由差异

兼容性公式：

```
is_compatible(client, server) =
    client.major == server.major
    AND client.minor == server.minor
```

### v1.0+（MAJOR ≥ 1，稳定阶段）

- **MAJOR 必须严格匹配**
- 在同一 MAJOR 内，Server MINOR **必须 ≥** Client MINOR
- PATCH 可自由差异

兼容性公式：

```
is_compatible(client, server) =
    client.major == server.major
    AND client.major >= 1
    AND client.minor <= server.minor
```

**说明**：

- 较新的 Server 能接纳较旧的 Client（向后兼容）
- 较旧的 Server **拒绝**较新的 Client（因为 Server 无法理解 Client 所用的新特性，可能在路由新事件时出错）
- 升级节奏：**Server 先于 Client 升级**

### 判定函数参考实现

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ProtocolVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> "ProtocolVersion":
        parts = s.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version: {s}")
        return cls(int(parts[0]), int(parts[1]), int(parts[2]))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def is_compatible(client: ProtocolVersion, server: ProtocolVersion) -> bool:
    """判定 Client 是否能连接到 Server。"""
    if client.major != server.major:
        return False
    if client.major == 0:
        # v0.x 严格匹配 MINOR
        return client.minor == server.minor
    # v1.0+ 向后兼容（Server MINOR >= Client MINOR）
    return client.minor <= server.minor
```

---

## 连接握手流程

### 1. Client 在 URL 中声明版本

客户端（Agent / Computer）通过 Socket.IO 连接 Server 时，在 **URL query string** 中携带 `a2c_version` 参数：

```
wss://server.example.com/smcp/?a2c_version=0.2.0
```

客户端代码示例：

```python
# Python 客户端
import socketio
from a2c_smcp import PROTOCOL_VERSION

sio = socketio.AsyncClient()
await sio.connect(
    f"wss://server.example.com?a2c_version={PROTOCOL_VERSION}",
    socketio_path="/smcp",
    auth={"role": "agent"},  # 业务层身份数据
)
```

```typescript
// TypeScript 客户端
import { io } from "socket.io-client";
import { PROTOCOL_VERSION } from "@a2c-smcp/client";

const socket = io("wss://server.example.com", {
  path: "/smcp",
  query: { a2c_version: PROTOCOL_VERSION },  // Socket.IO client 会自动拼接到 URL
  auth: { role: "agent" },
});
```

### 2. Server 在 HTTP 中间件层校验（实现无关的语义约束）

Server **MUST** 在任何 Socket.IO handler 执行**之前**，于 HTTP 层校验 URL query 中的 `a2c_version`。校验时机的强约束：

| 约束 | 说明 |
|------|------|
| **MUST** 在 Engine.IO HTTP 握手到达 Socket.IO 业务代码之前完成 | 确保 `connect` handler 即使有 bug 也无法绕过版本校验 |
| **MUST** 拦截所有 Engine.IO 握手 HTTP 请求（含 polling 与 WebSocket upgrade）| 任何路径的 Socket.IO 流量都要校验 |
| **不强制** HTTP 拦截路径 | 拦截路径由实现层/部署决定（见下） |

#### HTTP 拦截路径由实现决定（非协议常量）

下列概念属于不同抽象层，**协议层不规定**具体 HTTP URL 前缀：

| 概念 | 是什么 | 在哪里 | 协议是否规定 |
|------|------|------|------|
| Socket.IO **Namespace** `/smcp` | Socket.IO 协议层命名空间路由标签 | 报文 payload 内 | ✅ 协议固定为 `/smcp` |
| Engine.IO HTTP URL 路径 | 传输层 HTTP 握手 URL | HTTP URL（如 `/socket.io/` 或自定义）| ❌ 由 SDK / 部署决定 |

**默认路径在不同 SDK 中不一致**：

- **Python `python-socketio`**：默认 `/socket.io/`，可通过 `socketio_path="..."` 自定义（部分 python-sdk 实现使用 `socketio_path="/smcp"` 让 HTTP 路径与 namespace 同名）
- **Rust `socketioxide`**：默认 `/socket.io/`（Engine.IO 标准）
- **Node.js `socket.io`**：默认 `/socket.io/`

中间件 path 过滤逻辑**MUST**与所选 SDK 的实际 HTTP 挂载路径对齐——把"/smcp"硬编码到中间件 path 检查里在 Python 巧合可工作（当 socketio_path="/smcp"），但移植到 Rust 等 SDK 时会失效（Rust HTTP 路径仍是 `/socket.io/`，不会匹配 `/smcp` 前缀）。

#### 实现示例：Python（python-socketio + Starlette）

```python
# python-socketio + Starlette 示例
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount
from starlette.applications import Starlette
import socketio

SERVER_VERSION = ProtocolVersion(0, 2, 0)
# 此值与 socketio.ASGIApp(socketio_path=...) 保持一致——Python 实现选择，非协议常量
SMCP_HTTP_PATH = "/smcp"


class A2CVersionMiddleware(BaseHTTPMiddleware):
    """在 Socket.IO 处理前校验 a2c_version。"""
    async def dispatch(self, request, call_next):
        # 仅拦截 Socket.IO HTTP 流量；具体路径与 socketio_path 配置一致
        if not request.url.path.startswith(SMCP_HTTP_PATH):
            return await call_next(request)

        client_ver_str = request.query_params.get("a2c_version")
        if not client_ver_str:
            return JSONResponse(
                {"code": 400, "message": "Missing a2c_version query parameter"},
                status_code=400,
            )

        try:
            client_ver = ProtocolVersion.parse(client_ver_str)
        except ValueError as e:
            return JSONResponse(
                {"code": 400, "message": f"Invalid a2c_version: {e}"},
                status_code=400,
            )

        if not is_compatible(client_ver, SERVER_VERSION):
            return JSONResponse(
                {
                    "code": 4008,
                    "message": "Protocol version mismatch",
                    "server_version": str(SERVER_VERSION),
                    "client_version": str(client_ver),
                },
                status_code=400,
            )

        return await call_next(request)


sio = socketio.AsyncServer(async_mode="asgi")
sio_app = socketio.ASGIApp(sio, socketio_path="smcp")

app = Starlette(
    middleware=[Middleware(A2CVersionMiddleware)],
    routes=[Mount("/", sio_app)],
)
```

#### 实现示例：Rust（socketioxide + axum / tower）

Rust SDK 默认 HTTP 路径是 Engine.IO 标准 `/socket.io/`（与 Python 默认一致，但与 Python 的"自定义 `/smcp`"用法不同）。中间件应拦截**这个**路径：

```rust
// rust-sdk (socketioxide + axum) 伪代码示例
use axum::{
    http::{Request, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response, Json},
};
use serde_json::json;

const SERVER_VERSION: (u32, u32, u32) = (0, 2, 0);
// 与 SocketIo::builder() 实际 HTTP 挂载路径保持一致；socketioxide 默认 /socket.io/
const SMCP_HTTP_PATH: &str = "/socket.io/";

async fn a2c_version_middleware<B>(
    req: Request<B>,
    next: Next<B>,
) -> Result<Response, (StatusCode, Json<serde_json::Value>)> {
    let path = req.uri().path();
    if !path.starts_with(SMCP_HTTP_PATH) {
        return Ok(next.run(req).await);
    }

    let query = req.uri().query().unwrap_or("");
    let client_ver = parse_a2c_version_from_query(query)
        .ok_or((StatusCode::BAD_REQUEST, Json(json!({
            "code": 400,
            "message": "Missing a2c_version query parameter"
        }))))?;

    if !is_compatible(client_ver, SERVER_VERSION) {
        return Err((StatusCode::BAD_REQUEST, Json(json!({
            "code": 4008,
            "message": "Protocol version mismatch",
            "server_version": format_version(SERVER_VERSION),
            "client_version": format_version(client_ver),
        }))));
    }
    Ok(next.run(req).await)
}
```

**关键**：无论实现层用哪种语言/框架，中间件**必须早于** Socket.IO 业务 handler 执行——这是协议唯一规范的时机约束。版本不兼容的请求根本进不了 Socket.IO handler 层，即使 `connect` handler 有 bug 也无法绕过校验。

### 3. Client 处理 HTTP 400 错误

Socket.IO 客户端遇到 HTTP 400 响应会触发 `connect_error` 事件。SDK **必须**解析响应 body，识别 `code: 4008` 并抛出专属异常。

不同 Socket.IO 客户端库（python-socketio / socket.io-client / rust socketio crate）对 HTTP 错误 body 的封装格式不一，SDK **MUST** 容忍三种入参：

| 入参类型 | 触发场景 | 解析策略 |
|---|---|---|
| `dict` | python-socketio 自动反序列化 JSON 后传入 | 直接读取 |
| `str` | 客户端原样把 body 文本传入 | `json.loads()` 后读取；解析失败按"非协议错误"处理 |
| `bytes` | 部分底层客户端透传原始字节 | `bytes.decode("utf-8")` 后再走 `str` 路径；解码失败按"非协议错误"处理 |

参考解析器（python-sdk / rust-sdk **MUST 实现等价语义**）：

```python
# python-sdk 实现示例
import json
from typing import Any

def parse_connect_error(data: Any) -> dict | None:
    """统一三态入参 → dict | None；解析失败返回 None 表示"不是协议错误体"。"""
    if isinstance(data, dict):
        return data
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None
    return None


@sio.on("connect_error")
async def on_connect_error(data):
    payload = parse_connect_error(data)
    if payload and payload.get("code") == 4008:
        raise ProtocolVersionError(
            server_version=payload.get("server_version"),
            client_version=payload.get("client_version"),
            message=payload.get("message", "Protocol version mismatch"),
        )
    # 其他错误码处理...
```

该解析器是**SDK 层一次性代码**，对业务透明。所有 SDK 实现 SHOULD 复用此模板，避免在不同客户端库间分化。

#### 4. Client SDK MUST 主动断开连接

收到 `4008` 后 SDK **MUST** 主动调用底层 Socket.IO 客户端的 `disconnect()`（或等效操作）显式断开连接，**不依赖底层库默认行为**——

| SDK | 必需操作 |
|---|---|
| python-sdk | `await sio.disconnect()` 后再抛 `ProtocolVersionError` |
| rust-sdk | `socket.disconnect().await` 后再返回 `ProtocolVersionError` |
| Node SDK | `socket.disconnect()` 后再 emit error |

**理由**：多数 Socket.IO 客户端库（python-socketio、rust `rust_socketio`、Node `socket.io-client`）默认开启自动重连。若 SDK 不主动 disconnect，库会在收到 `connect_error` 后立即发起重连请求，再次触发 `4008`，进入死循环烧 CPU + 烧 Server 资源。

**MUST NOT**：

- 不得静默重试（连接已确认不兼容）
- 不得依赖客户端库的"自动停止重连"启发式（不同库语义不一致）
- 不得让用户业务代码处理重连（这是 SDK 层职责）

正确处理流程：

```
connect_error(payload) → 解析 payload → 识别 code:4008
    → SDK 主动 disconnect()
    → 抛 ProtocolVersionError(server_version, client_version) 到用户业务代码
    → 用户决定如何应对（升级 SDK / 切换 Server 实例 / 报告给运维）
```

---

## 错误码

### 4008 Protocol Version Mismatch

- **触发**：Client 在 Socket.IO 连接请求的 URL query 中声明的 `a2c_version` 与 Server 不兼容
- **作用**：阻止连接建立（HTTP 层直接返回 400，未进入 Socket.IO）
- **响应结构**（HTTP 400 body）：

```json
{
  "code": 4008,
  "message": "Protocol version mismatch",
  "server_version": "0.2.0",
  "client_version": "0.1.5"
}
```

Client SDK **必须**将此错误转换为明确异常，而不是静默重试。

---

## 版本号来源与发布流程

### 协议仓库（本仓库）

- 协议版本定义在 `pyproject.toml` 的 `version` 字段（`bump-my-version` 管理）
- 每次变更应同步更新本文档顶部的 **"当前协议版本"** 字段
- CHANGELOG（若有）记录 MAJOR / MINOR 级变更

### SDK 仓库

SDK 包版本号与协议版本号的关系**MUST**遵循以下规则：

| 维度 | 约束 |
|------|------|
| **SDK MAJOR.MINOR** | **MUST** 与所实现的协议 MAJOR.MINOR 严格相等（如协议 `0.2.0`，SDK 包版本 MUST 为 `0.2.x`）|
| **SDK PATCH** | **自由**——留给 SDK 实现层的 bug 修复、性能优化、依赖升级（如 rust-sdk `0.2.0` → `0.2.1` 修一个反序列化 bug，仍实现协议 `0.2.0`）|
| **PROTOCOL_VERSION 常量** | SDK 在代码中显式导出所实现的协议版本（与 SDK 包版本通常 MAJOR.MINOR 相同，PATCH 可能不同）|

**收益**：

- 用户从 SDK 包版本第一眼就能判断目标协议版本（`pip install a2c-smcp==0.2.5` ⇒ 协议 0.2.x）
- SDK 修 bug 时不污染协议版本（rust-sdk `0.2.1` 不意味协议改动）
- 协议升级时 SDK 必须同步（消除"SDK 老 + 协议新"的漂移可能）

**rust-sdk / python-sdk 升级路径**（首次实现 v0.2 时）：

```
rust-sdk 0.1.15 (协议 0.1.x) → 0.2.0 (协议 0.2.0)         # MAJOR.MINOR 跳到 0.2 锚定协议
rust-sdk 0.2.0 → 0.2.1 (协议仍 0.2.0)                     # SDK bug fix，PATCH 自由

python-sdk 0.1.5 (协议 0.1.x) → 0.2.0 (协议 0.2.0)        # 同上
```

- 每个 SDK 包必须在代码中导出**它所实现的协议版本**常量：

```python
# python-sdk
from a2c_smcp import PROTOCOL_VERSION  # "0.2.0"
```

```rust
// rust-sdk
pub const PROTOCOL_VERSION: &str = "0.2.0";
```

- 客户端 SDK 在连接时自动从该常量读取 `a2c_version` 拼入 URL，**禁止**让用户代码手动传入

### Server 实现

- Server 实现者（python-sdk 的 server 模块 / 用户自建 Server）在启动时必须声明自己的协议版本
- 建议暴露为命令行参数或环境变量，便于运维切换

---

## 多版本部署模式

需要同时支持多个协议版本客户端时，**不要**让单个 Server 实例支持多版本，而是：

### 模式 1：独立实例 + DNS 分流

```
v0.1 客户端 → wss://v01.server.example.com → Server v0.1 实例
v0.2 客户端 → wss://v02.server.example.com → Server v0.2 实例
```

### 模式 2：路径分流

```
v0.1 客户端 → wss://server.example.com/smcp/v0.1 → Server v0.1 实例
v0.2 客户端 → wss://server.example.com/smcp/v0.2 → Server v0.2 实例
```

### 模式 3：单实例滚动升级（仅 v1.0+）

在 v1.0+ 稳定阶段：

1. 先升级所有 Server 实例到新 MINOR（兼容老 Client）
2. 逐步升级 Client
3. 完成后新旧 Client 共存于同一 Server

v0.x 阶段不适用该模式（因为 MINOR 也可能是破坏性），需走模式 1 或 2。

---

## 版本协商的非目标

本规范**不包含**以下设计，以控制复杂度：

- ❌ **Capabilities / 特性发现**：v0.x 阶段协议是一个整体，实现即完整实现；未来若需要特性级粒度（如"实现了 v1.2 但没实现可选特性 X"），届时再引入
- ❌ **自动协商降级**（MCP 风格）——Client 和 Server 不会自动选择更低版本通信
- ❌ **Server 同时支持多版本 Client**——通过部署拓扑解决
- ❌ **Peer-to-peer 版本协商**——通过 "Server 锚点 + 传递性" 解决

这些在 v0.x 阶段被**有意排除**以降低实现复杂度。v1.0+ 进入稳定阶段后可根据实际需要再引入。

---

## 测试建议

SDK 测试应覆盖以下场景：

| 场景 | Client 版本 | Server 版本 | 预期 |
|---|---|---|---|
| 完全匹配 | 0.2.0 | 0.2.0 | ✅ 连接 |
| PATCH 差异 | 0.2.1 | 0.2.0 | ✅ 连接 |
| MINOR 差异（v0.x） | 0.2.0 | 0.3.0 | ❌ HTTP 400 / 4008 |
| MINOR 差异（v0.x 反向） | 0.3.0 | 0.2.0 | ❌ HTTP 400 / 4008 |
| MAJOR 差异 | 1.0.0 | 0.2.0 | ❌ HTTP 400 / 4008 |
| v1.0 向后兼容 | 1.0.0 | 1.2.0 | ✅ 连接 |
| v1.0 Client 更新 | 1.2.0 | 1.0.0 | ❌ HTTP 400 / 4008 |
| 缺失 a2c_version | — | 0.2.0 | ❌ HTTP 400 |
| 非法版本号 | "abc" | 0.2.0 | ❌ HTTP 400 |
| 中间件前置性 | connect handler 故意抛异常 | 0.2.0 | 版本校验仍正常工作（业务代码不影响协议校验） |

---

## 参考

- [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html)
- [Socket.IO handshake](https://socket.io/docs/v4/how-it-works/#handshake)
- [错误处理](error-handling.md#协议版本不匹配4008)
- [数据结构](data-structures.md#房间管理结构)
- [事件定义](events.md#连接握手)
