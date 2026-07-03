# Connection Management

本文定义 Computer Management Plane 中 Computer runtime 与 SMCP Server / robot / Office 的连接管理语义。

Computer runtime 可以已经从 `ComputerHome` 启动并处于 `ready`，但尚未连接任何 SMCP Server / robot / Office。连接状态与 lifecycle 状态是两个独立维度：

```
Computer lifecycle: ready
Connection state:   disconnected
```

这表示本地 Computer 可管理、配置可修改、MCP/SKILL/plugin 可 reconcile，但 Agent 暂时看不到该 Computer，Computer 也不发送 `server:update_*`。

## 1. 管理范围

本模块管理：

- SMCP Server / robot endpoint 配置。
- 连接 auth payload 或 credential reference。
- connect / disconnect / reconnect。
- join office / leave office。
- online / offline / reconnecting / auth_failed 等连接状态。
- 未连接时管理面操作如何处理。
- 连接成功后如何发布当前 Agent-facing projection。
- 断线期间 update notification 的处理边界。

本模块不管理：

- 从 `ComputerHome` 启动 Computer runtime，见 [Lifecycle](lifecycle.md)。
- Socket.IO wire 握手细节，见 [事件定义 §连接握手](../events.md#连接握手)。
- Server 侧房间隔离规则，见 [房间隔离模型](../room-model.md)。

## 2. 状态语义

| 状态 | 含义 | Agent-facing 投影 |
|---|---|---|
| `disconnected` | runtime 未连接 SMCP Server / robot | Agent 不可见；不发送 `server:update_*` |
| `connecting` | 正在连接 Server / robot | 暂不保证 Agent 可见 |
| `connected` | Socket.IO 已连接，但可能未加入 Office | 取决于 Office 状态 |
| `joining_office` | 正在发送 `server:join_office` | 暂不保证 Agent 可见 |
| `online` | 已连接并成功加入 Office | Agent 可通过 Server 路由访问 |
| `reconnecting` | 连接中断后正在重连 | 管理面仍可修改 desired state |
| `auth_failed` | 连接或 join 因认证失败 | Agent 不可见；管理面返回诊断 |
| `connection_failed` | 网络、版本或 Server 拒绝导致失败 | Agent 不可见；管理面返回诊断 |

连接状态属于管理面诊断，不直接进入 Agent-facing `client:*` 响应。

## 3. Connection Config

管理面 MAY 持久化或引用下列连接配置：

| 配置 | 语义 |
|---|---|
| endpoint | SMCP Server / robot 的连接地址 |
| namespace | Socket.IO namespace，默认仍应符合 `/smcp` 协议约定 |
| office_id | 要加入的 Office |
| computer_name | Server 路由该 Computer 的协议名 |
| auth reference | 连接认证所需 secret 的本地引用 |
| reconnect policy | 自动重连、退避、最大次数等策略 |

auth secret 明文 SHOULD 存在于本地 secret manager / keychain；`ComputerHome` 内 SHOULD 只保存引用或非敏感元数据。Computer MUST NOT 通过 Agent-facing 响应暴露 endpoint credential 或 auth payload。

## 4. Operations

| 能力 | 语义 | 完成后的协议投影 |
|---|---|---|
| configure connection | 设置 endpoint、office、computer name、auth reference 等 | 不要求通知 |
| connect | 建立 Socket.IO 连接并准备 join office | 连接成功前 Agent 不可见 |
| join office | 加入目标 Office | 成功后 Agent 可路由到该 Computer |
| disconnect | 断开连接，可保留 runtime ready | Agent 不再可路由到该 Computer |
| leave office | 离开 Office 但可保持底层连接 | Agent 不再可按该 Office 访问 |
| reconnect | 断线后重新连接并重新 join office | 成功后恢复 Agent-facing 路由 |
| get connection status | 查看 online/auth_failed/last error 等诊断 | 不进入 Agent-facing 协议 |

`connect` 成功不等价于 Agent 已看到最新工具或 SKILL。连接进入 `online` 后，Agent 仍通过 `client:get_*` 拉取当前 projection。

## 5. 未连接时的管理操作

当 connection state 不是 `online` 时，管理面仍 MAY 允许修改 desired state，例如安装 plugin、启用 MCP Server、隐藏 SKILL 或修改 tool policy。

未连接期间：

1. Computer SHOULD 更新本地 desired state 和 runtime projection。
2. Computer MUST NOT 发送 `server:update_*`，因为没有有效 Office 路由。
3. 连接恢复并进入 `online` 后，Agent 应通过初始或主动 `client:get_*` 获取当前 projection。

实现 MAY 在重连成功后发送必要的 `server:update_*` 作为刷新提示，但不得依赖这些通知承载完整状态。

## 6. 断线期间的更新

如果 Computer 曾经 `online`，随后断线，断线期间发生的管理面变化可以被：

- 合并为 dirty flags。
- 仅更新本地 projection。
- 在 reconnect 成功后发送一次或多次 `server:update_*`。
- 等待 Agent 主动拉取。

协议不规定 debounce/coalescing 策略。要求是 reconnect 后 Agent 通过对应 `client:get_*` MUST 能读到当前已成功 reconcile 的 projection。

## 7. 多连接边界

默认情况下，一个 Computer runtime SHOULD 在同一时刻绑定一个 active Office。若 SDK 支持多 robot / 多 Office 连接，必须保证：

1. 不同 Office 的 Agent-facing projection 不发生越权混用。
2. `server:update_*` 只发送到对应连接/Office。
3. secret、BlobHandle、SKILL 访问与工具调用仍遵守房间隔离和 Computer 本地安全边界。

多连接支持属于 SDK guidance；A2C-SMCP 的基础协议仍以单个 Computer 加入一个 Office 的模型为准。

