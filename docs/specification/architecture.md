# A2C-SMCP 架构设计

本文档描述 A2C-SMCP 协议的架构设计，包括角色关系、通信模型和核心组件。

## 角色与关系

### 三角色模型

A2C-SMCP 协议定义了三个核心角色：

```
┌─────────────────────────────────────────────────────────────┐
│                        A2C-SMCP 系统                         │
│                                                              │
│  ┌──────────┐       ┌──────────┐       ┌──────────────────┐ │
│  │          │       │          │       │                  │ │
│  │  Agent   │◄─────►│  Server  │◄─────►│    Computer      │ │
│  │          │       │          │       │                  │ │
│  └──────────┘       └──────────┘       └──────────────────┘ │
│       │                  │                      │           │
│       │                  │                      │           │
│  工具调用          信令服务器              MCP 服务管理      │
│  发起方            连接管理                工具执行          │
│                    消息路由                                  │
│                    通知广播                                  │
└─────────────────────────────────────────────────────────────┘
```

### 角色职责

| 角色 | 职责 | 数量约束 |
|------|------|---------|
| **Agent** | 工具调用发起方，通常为智能体、机器人等业务系统 | 每个房间最多 1 个 |
| **Server** | 信令中枢，负责连接管理、房间管理、消息路由和通知广播 | 全局 1 个（逻辑） |
| **Computer** | MCP Server 宿主，统一管理多个 MCP 服务并对外暴露工具 | 每个房间可多个 |

### 角色关系约束

1. **Agent 独占性**: 一个房间内最多只能有一个 Agent
2. **Computer 绑定性**: 一个 Computer 在同一时刻只能属于一个房间
3. **Server 中心性**: 所有 Agent 和 Computer 之间的通信必须经过 Server

---

## 通信模型

### 传输层

A2C-SMCP 协议运行在 Socket.IO 之上：

```
┌─────────────────────────────────────┐
│           A2C-SMCP 协议              │
├─────────────────────────────────────┤
│           Socket.IO                  │
├─────────────────────────────────────┤
│      WebSocket / HTTP 长轮询         │
├─────────────────────────────────────┤
│           TCP/TLS                    │
└─────────────────────────────────────┘
```

### 命名空间

所有协议事件通过统一命名空间传输：

```python
SMCP_NAMESPACE = "/smcp"
```

### 消息流向

```
             client:*                     client:*
    Agent ─────────────→ Server ─────────────→ Computer
      │                    │                      │
      │                    │                      │
      │    notify:*        │       server:*       │
      ◄────────────────────┤◄─────────────────────┤
                           │
                           │ notify:* (广播)
                           ▼
                    房间内所有成员
```

---

## 事件路由机制

### 事件前缀约定

| 前缀 | 方向 | 处理方 | 说明 |
|------|------|--------|------|
| `client:` | Agent → Computer | Computer | 由 Server 路由到指定 Computer |
| `server:` | 客户端 → Server | Server | 由 Server 直接处理 |
| `notify:` | Server → 广播 | Agent/Computer | 广播到房间内所有成员 |

### 路由流程

#### Client 事件路由

```
1. Agent 发送 client:tool_call，指定目标 computer
2. Server 接收事件
3. Server 验证 Agent 和 Computer 在同一房间
4. Server 通过 name → sid 映射找到目标 Computer
5. Server 转发事件到 Computer
6. Computer 执行并返回结果
7. Server 将结果返回给 Agent
```

#### Server 事件处理

```
1. 客户端发送 server:join_office
2. Server 接收并验证请求
3. Server 执行房间加入逻辑
4. Server 返回处理结果
5. Server 广播 notify:enter_office 到房间
```

---

## 核心组件

### Server 端组件

```
a2c_smcp/server/
├── auth.py           # 认证系统（AuthenticationProvider）
├── base.py           # 基础命名空间（BaseNamespace）
├── namespace.py      # SMCP 协议命名空间（SMCPNamespace）
├── sync_namespace.py # 同步版本命名空间
├── types.py          # 类型定义
└── utils.py          # 工具函数
```

**核心类**:

- `AuthenticationProvider`: 认证抽象基类
- `BaseNamespace`: 基础命名空间，提供连接管理和 name 映射
- `SMCPNamespace`: SMCP 协议实现，处理所有协议事件

### Agent 端组件

```
a2c_smcp/agent/
├── auth.py         # Agent 认证提供者
├── base.py         # 基础客户端抽象
├── client.py       # 异步客户端（AsyncSMCPAgentClient）
├── sync_client.py  # 同步客户端（SMCPAgentClient）
└── types.py        # 类型定义和事件处理协议
```

**核心类**:

- `AgentAuthProvider`: Agent 认证抽象基类
- `AsyncSMCPAgentClient`: 异步 Agent 客户端
- `SMCPAgentClient`: 同步 Agent 客户端

### Computer 端组件

```
a2c_smcp/computer/
├── computer.py           # Computer 主类
├── base.py               # 基础抽象类
├── socketio/
│   └── client.py         # Socket.IO 客户端（SMCPComputerClient）
├── mcp_clients/
│   ├── manager.py        # MCP 服务器管理器
│   ├── base_client.py    # MCP 客户端基类
│   ├── stdio_client.py   # Stdio 客户端
│   ├── sse_client.py     # SSE 客户端
│   └── http_client.py    # HTTP 客户端
├── desktop/
│   └── organize.py       # 桌面组织逻辑
└── inputs/
    └── resolver.py       # 输入解析器
```

**核心类**:

- `Computer`: Computer 主类，管理 MCP 服务器和工具
- `SMCPComputerClient`: Socket.IO 客户端，处理 SMCP 协议通信
- `MCPServerManager`: MCP 服务器生命周期管理

---

## Name 映射系统

Server 通过 name 映射系统实现 Agent/Computer 的定位：

```
┌─────────────────────────────────────────────┐
│              Server 内部状态                 │
├─────────────────────────────────────────────┤
│                                              │
│  name_to_sid: dict[str, str]                │
│    "agent-1"    → "abc123..."               │
│    "computer-1" → "def456..."               │
│    "computer-2" → "ghi789..."               │
│                                              │
│  sessions: dict[str, Session]               │
│    "abc123..." → {name, role, office_id}    │
│    "def456..." → {name, role, office_id}    │
│                                              │
└─────────────────────────────────────────────┘
```

### 映射生命周期

1. **注册**: 客户端加入房间时，注册 name → sid 映射
2. **查询**: 路由事件时，通过 name 查找目标 sid
3. **注销**: 客户端断开连接或离开房间时，清除映射

---

## 房间模型

### 房间结构

```
┌─────────────────────────────────────────────┐
│              Office (Room)                   │
│              office_id: "room-001"           │
├─────────────────────────────────────────────┤
│                                              │
│  Agent: agent-1 (sid: abc123)               │
│                                              │
│  Computers:                                  │
│    - computer-1 (sid: def456)               │
│    - computer-2 (sid: ghi789)               │
│                                              │
└─────────────────────────────────────────────┘
```

### 隔离保障

| 约束 | 说明 |
|------|------|
| Agent 独占 | 房间已有 Agent 时，拒绝新 Agent 加入 |
| Computer 绑定 | Computer 加入新房间时，自动离开旧房间 |
| 跨房间禁止 | 不允许访问其他房间的资源 |

---

## 与 MCP 的集成

Computer 作为 MCP Server 的宿主，实现了与 MCP 协议的桥接：

```
┌─────────────────────────────────────────────────────────┐
│                      Computer                            │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │              MCPServerManager                    │    │
│  │                                                  │    │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐     │    │
│  │   │MCP Client│  │MCP Client│  │MCP Client│     │    │
│  │   │ (Stdio)  │  │  (SSE)   │  │(Streamable)│   │    │
│  │   └────┬─────┘  └────┬─────┘  └────┬─────┘     │    │
│  └────────┼─────────────┼─────────────┼───────────┘    │
│           │             │             │                 │
│           ▼             ▼             ▼                 │
│      ┌────────┐    ┌────────┐    ┌────────┐            │
│      │MCP Srv1│    │MCP Srv2│    │MCP Srv3│            │
│      └────────┘    └────────┘    └────────┘            │
└─────────────────────────────────────────────────────────┘
```

### 工具聚合

1. Computer 从多个 MCP Server 收集工具定义
2. 统一转换为 `SMCPTool` 格式
3. 通过别名机制解决工具名冲突
4. 对外暴露统一的工具视图

### Desktop 桌面系统

Computer 将多个 MCP Server 暴露的 `window://` 资源聚合为统一的桌面视图，为 Agent 提供工具调用之外的上下文信息。

```
MCP Server A ──┐
  window://a/.. │    ┌─────────────────┐         ┌─────────┐
               ├───→│    Computer      │────────→│  Agent   │
MCP Server B ──┤    │ Desktop Organizer│         │          │
  window://b/.. │    └─────────────────┘         └─────────┘
               │         过滤/排序/截断
MCP Server C ──┘
  (无窗口资源)
```

**MCP 操作到 Desktop 的映射**:

| MCP 操作 | Desktop 用途 |
|----------|-------------|
| `resources/list` | 枚举并筛选 `window://` 资源 |
| `resources/read` | 读取窗口的文本内容 |
| `resources.subscribe` 能力 | 前提条件，Computer 据此决定是否枚举该 Server 的窗口 |
| `ResourceListChangedNotification` | 触发窗口集合变化检测 |
| `ResourceUpdatedNotification` | 触发窗口内容变化刷新 |

**核心组件**:

- `desktop/organize.py` — 桌面组织策略（过滤、排序、全屏处理、截断）
- `utils/window_uri.py` — `window://` URI 解析与构建

详见 [Desktop 桌面系统](desktop.md) 完整规范。

### Finder 文档系统

Computer 将多个 MCP Server 暴露的 `dpe://` 资源聚合为统一的文档目录视图，为 Agent 提供结构化文档的渐进式导航能力。

```
MCP Server A ──┐
  dpe://a/..   │    ┌─────────────────┐         ┌─────────┐
               ├───→│    Computer     │────────→│  Agent  │
MCP Server B ──┤    │ Finder Organizer│         │         │
  dpe://b/..   │    └─────────────────┘         └─────────┘
               │         过滤/排序/分页
MCP Server C ──┘
  (无文档资源)
```

**MCP 操作到 Finder 的映射**:

| MCP 操作 | Finder 用途 |
|----------|------------|
| `resources/list` | 枚举并筛选 `dpe://` 资源 |
| `resources/read` | 按 URI 级别读取文档/页面/元素内容 |
| `resources/templates` | 声明 `pages/{N}` 和 `elements/{ID}` 子路径模板 |
| `resources.subscribe` 能力 | 前提条件，Computer 据此决定是否枚举该 Server 的文档 |
| `ResourceListChangedNotification` | 触发文档集合变化检测 |
| `ResourceUpdatedNotification` | 触发文档内容变化刷新 |
| `completion/complete` | 可选：`dpe://` 资源模板参数自动补全 |

**核心组件**:

- `finder/organize.py` — Finder 组织策略（过滤、排序、分页）
- `utils/dpe_uri.py` — `dpe://` URI 解析与构建

详见 [Finder 文档系统](finder.md) 完整规范。

---

## 同步/异步双栈

Server 和 Agent 模块均提供同步和异步两种实现：

| 模块 | 异步实现 | 同步实现 |
|------|---------|---------|
| Server | `SMCPNamespace` | `SyncSMCPNamespace` |
| Agent | `AsyncSMCPAgentClient` | `SMCPAgentClient` |

**注意**: 修改协议逻辑时，必须同时更新两个版本以保持一致性。

---

## 参考

- Server 实现: `a2c_smcp/server/`
- Agent 实现: `a2c_smcp/agent/`
- Computer 实现: `a2c_smcp/computer/`
- 协议定义: `a2c_smcp/smcp.py`
