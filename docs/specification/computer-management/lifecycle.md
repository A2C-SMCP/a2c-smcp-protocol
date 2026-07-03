# Computer Management Lifecycle

本文定义 Computer Management Plane 的整体生命周期。它管理可信本地客户端如何通过一个 `ComputerHome` 实例化 Computer runtime，并约束 desired state 持久化、启动、关闭、reload、迁移与并发边界。

## 1. 管理范围

本模块管理：

- `ComputerHome` 作为 SDK/admin surface 的本地持久化根。
- 从 `ComputerHome` 实例化 Computer 的启动流程。
- home ownership、进程并发、schema version 与 migration。
- desired state 在 home 下的持久化边界。
- 管理面可用状态：`uninitialized`、`booting`、`ready`、`degraded`、`shutting_down`、`stopped`。
- Computer runtime 的启动、关闭、reload 与本地状态重载。
- desired state 与 runtime state 的基本关系。
- 管理操作成功返回与 Agent 已观察更新之间的边界。
- 并发管理操作的串行化、幂等与冲突处理原则。

本模块不管理：

- 单个 MCP Server 的配置和启停细节，见 [MCP Server](mcp-server.md)。
- 单个 SKILL、plugin 或 marketplace source 的业务状态。
- 跨 SDK 共享 home 的目录布局、文件名或序列化格式。
- Computer runtime 与 SMCP Server / robot / Office 的连接、断开、重连、join/leave office，见 [Connection Management](connection.md)。
- Agent-facing Socket.IO 连接握手和 Office 隔离，见 [Computer 侧协议框架](../computer.md)。

本模块中的 `ComputerHome`、状态名、boot sequence、ownership 和 migration 规则是 SDK guidance，除非它们影响 Agent-facing projection 或 secret/file-access 安全边界。跨语言协议 conformance 不要求不同 SDK 共享同一个 home，也不要求同一目录布局、schema 文件名、锁实现或 migration 算法。

## 2. ComputerHome Contract

`ComputerHome` 是可信本地客户端提供给 SDK 的持久化根。SDK 可以使用该 home 实例化一个 Computer，并把本地管理面所需的 durable desired state 存储在该 home 下，或在该 home 下存储外部 secret / cache / package store 的安全引用。

Computer SDK SHOULD 支持从一个明确的 `ComputerHome` 启动 Computer Management Plane。若 SDK 也支持默认 home 解析，该解析策略属于 SDK guidance，不进入 A2C-SMCP 协议。

`ComputerHome` MUST NOT 通过 Agent-facing SMCP 事件暴露给 Agent。Computer MUST NOT 允许 Agent 通过 `client:get_config`、`client:get_skill`、`client:get_blob`、`client:get_desktop` 或 tool metadata 读取 home 下任意文件。

The normative requirement is the negative security boundary above. The existence of a home path, default home discovery, directory names, schema manifest and package/cache placement are not protocol fields.

## 3. Home Binding

可信本地客户端绑定 `ComputerHome` 时，管理面 SHOULD 建立如下语义：

| 绑定项 | 语义 |
|---|---|
| home identity | 同一个 home 表示同一个本地 Computer 管理域 |
| durable desired state | MCP Server 配置、tool exposure policy、SKILL exposure、marketplace、plugin、input definitions 等从 home 加载 |
| runtime projection | SDK 从 desired state reconcile 出 Agent-facing config/tools/skills/Desktop |
| diagnostics | runtime health、last error、reconnect 状态、安装诊断等 MAY 存储或缓存于 home |
| secret boundary | secret 明文 SHOULD 存在于本地 secret manager / keychain；home 内 SHOULD 只保存引用或非敏感元数据 |

本规范不要求不同语言 SDK 能共享同一个 home，也不要求固定子目录名。若某 SDK 选择 `config/`、`state/`、`skills/`、`plugins/`、`marketplaces/`、`cache/`、`logs/` 等布局，这些布局属于该 SDK 的实现指南。

## 4. Home Ownership

Computer SDK SHOULD 避免多个 writer 同时修改同一个 `ComputerHome`。实现可以使用进程锁、文件锁、宿主应用单例、管理面代理或其它等价机制。

如果 SDK 允许多个进程同时访问同一 home，SHOULD 明确区分 writer 与 read-only observer。多个 writer 对同一 durable desired state 的并发写入 SHOULD 被串行化或拒绝为 conflict。

Home ownership 错误属于 management lifecycle 错误，不映射为 Agent-facing `ErrorPayload`。

## 5. Home Schema 与 Migration

`ComputerHome` SHOULD 具有可识别的 schema/version manifest 或等价机制。SDK 打开 home 时 SHOULD 先检查版本兼容性：

1. 兼容版本：继续加载 desired state。
2. 可迁移版本：先完成 migration，再加载 desired state。
3. 不兼容版本：拒绝启动或进入 `degraded`，并返回管理面 validation/lifecycle 错误。

Migration MUST NOT 绕过 Agent-facing 安全边界。迁移期间不得把 secret 明文写入 Agent-facing projection。Migration ordering, file formats and rollback strategy are SDK guidance.

## 6. Boot Sequence

从 `ComputerHome` 启动 Computer Management Plane 时，推荐顺序为：

1. 绑定并校验 `ComputerHome`。
2. 获取 home ownership。
3. 读取 home schema/version。
4. 必要时执行 migration。
5. 加载 durable desired state。
6. 初始化 registry、policy、input definitions 与本地引用。
7. reconcile MCP Server、plugin、marketplace、SKILL 与 tool exposure。
8. 构建 Agent-facing projection。
9. 进入 `ready` 或 `degraded`。

该顺序是 SDK guidance；协议要求是启动完成后 Agent-facing 投影必须与已成功加载和 reconcile 的 desired state 一致。

## 7. 状态语义

| 状态 | 含义 | 管理操作 |
|---|---|---|
| `uninitialized` | 管理面尚未绑定或加载 `ComputerHome` | SHOULD 只接受初始化类操作 |
| `booting` | Computer 正在校验 home、加载 desired state 或恢复索引 | SHOULD 拒绝冲突性 mutation，MAY 接受查询 |
| `ready` | 管理面可接受查询和 mutation | 正常可用 |
| `degraded` | 部分子系统失败，但管理面仍可响应 | SHOULD 返回诊断并允许修复操作 |
| `shutting_down` | 正在停止 runtime 或释放资源 | SHOULD 拒绝新的 mutation |
| `stopped` | runtime 已停止 | MAY 接受配置类 mutation，能力不可投影给 Agent |

这些状态属于管理面诊断，不直接进入 Agent-facing `client:*` 响应。

## 8. 操作类别

| 操作类别 | 示例 | 预期 |
|---|---|---|
| boot | 绑定 home、启动 Computer runtime、加载配置、初始化 registry | 成功后进入 `ready` 或 `degraded` |
| shutdown | 停止 runtime、断开 MCP Server、停止 watcher | 成功后进入 `stopped` |
| reload | 重读本地 desired state 并 reconcile | 变化时触发对应 update notification |
| reset local state | 清理管理面缓存或诊断状态 | MUST NOT 删除 durable desired state，除非调用方明确要求 |
| repair home | 尝试修复 schema、索引或 partial migration 状态 | 成功后重新 reconcile |
| query | 查询状态、诊断、配置视图 | SHOULD 在多数状态下可用 |

## 9. Connection 关系

Lifecycle 只决定 Computer runtime 是否已经从 `ComputerHome` 启动并可被本地管理。Computer 是否连接到 SMCP Server / robot / Office 由 [Connection Management](connection.md) 管理。

管理面可以在 Computer 未连接或未加入 Office 时修改 desired state。若 connection state 不是 `online`，管理操作完成后不应发送 `server:update_*`；Computer 后续连接并进入 `online` 后，Agent 应通过初始或主动 `client:get_*` 拉取当前投影。

管理操作成功返回只表示 Computer 已接受或完成 desired state 变更，不表示 Agent 已收到 `notify:*` 或已重新拉取。

## 10. 并发与幂等

Computer Management Plane SHOULD 对会修改同一对象集合的操作进行串行化或冲突检测。重复执行下列操作 SHOULD 是幂等的，或返回明确的 conflict / validation 错误：

- boot with same home
- enable / disable
- expose / hide
- install 已安装对象
- remove 不存在对象
- sync marketplace
- reload

冲突和 partial failure 的错误分类见 [Management Errors](errors.md)。
