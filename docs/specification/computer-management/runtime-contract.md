# Computer 运行时契约（Runtime Contract）

本文定义业务 client 可以跨 SDK 依赖的单个 Computer runtime 公共语义。它不是 wire protocol，也不规定 Python、Rust、TypeScript 或其它 SDK 的代码形态。

Runtime contract 的目标是：同一份声明式 `ComputerConfig` 和 `RuntimeOptions` 在不同 SDK 中产生等价 runtime intent，并通过一致的生命周期、错误分类、marketplace/plugin 挂载、`sync_config` final state 和 shutdown 语义交付给业务 client。

## 1. 边界

Runtime contract 负责：

- 从声明式 config 创建一个 runtime Computer。
- 启动、停止、连接、断开、同步配置、关闭一个 runtime Computer。
- 默认值解析、生命周期状态、错误分类和 retryability。
- marketplace / plugin / user / MCP source 能力挂载语义。
- 单个 runtime 与 Agent-facing protocol projection 的一致性。
- 共享 JSON fixture 与生命周期 conformance tests。

Runtime contract 不负责：

- 多 Computer 编排、UI 状态、账号选择、Server 选择、office 策略和审计流。
- Python dataclass、Rust builder、TypeScript constructor、trait 名、class 名或 method 名。
- 内部缓存、锁、watcher、目录布局、进程模型、async runtime、CLI UX。

## 2. 核心对象

### 2.1 ComputerConfig

SDK SHOULD 接受一个声明式 config 对象，并具备以下语义内容：

| 字段族 | 稳定语义预期 |
|---|---|
| identity | Computer protocol name 和可选本地展示元数据 |
| mcp_servers | MCP Server configs、disabled flags、forbidden tools、tool metadata 和 transport parameters |
| inputs | 用于本地渲染 MCP Server configs 的 input definitions |
| skills | User DropIn roots 或等价本地 SKILL source declarations |
| marketplaces | Known marketplace source declarations 和 trust/update policy |
| plugins | Installed/enabled plugin declarations 和 plugin-scoped capability intent |
| settings_policy | Scope merge result 或等价治理策略 |
| connection | 可选默认 Server URL、namespace、office 和 auth payload policy |

不同 SDK 的 config shape 可以不同，但共享 conformance fixtures MUST 能表达为 JSON，并映射为等价 runtime intent。

### 2.2 RuntimeOptions

SDK SHOULD 接受 runtime options，用于表达环境相关行为：

| 选项族 | 稳定语义预期 |
|---|---|
| home | 可选本地 Computer home 或 storage root |
| workdirs | 用于 capability discovery 的 registered workdirs |
| secret providers | 本地 input/secret resolver hooks |
| auth payload provider | 用于添加非 A2C 业务 auth fields 的 callback 或 value |
| network options | Socket.IO path、namespace、transport、timeout 和 reconnect options |
| blob thresholds | inline、too-large 和 chunk-size budgets |
| policy hooks | 本地 source trust、plugin approval 和 management authorization hooks |
| diagnostics hooks | logging、metrics 和 health observers |

RuntimeOptions MAY 使用 SDK-specific 名称和默认值。最终外部可见行为 MUST 符合本 contract。

## 3. 生命周期状态

SDK SHOULD 暴露生命周期状态或等价公开诊断，并具备以下语义：

| 状态 | 含义 |
|---|---|
| `created` | Runtime object 已存在，但尚未初始化本地资源 |
| `starting` | Runtime 正在加载 config、解析本地状态或启动 MCP 资源 |
| `started` | 本地 runtime 已初始化；可能已连接或未连接 SMCP Server |
| `connecting` | Runtime 正在建立 Socket.IO 连接并执行协议握手 |
| `connected` | Socket.IO 连接已建立，但 Office join 可能尚未完成 |
| `joined_office` | Computer 已加入 Office，可以接收路由来的 `client:*` events |
| `syncing` | Runtime 正在应用新 config 或 reconcile desired state |
| `degraded` | Runtime 部分可用，并带有公开诊断 |
| `disconnecting` | Runtime 正在离开或关闭 Socket.IO 连接 |
| `stopping` | Runtime 正在停止本地 MCP/service activity |
| `stopped` | Runtime 已停止 service activity |
| `shutdown` | Runtime 已释放资源，不应再发出 stale events |
| `error` | Runtime 在没有外部动作或新 config 的情况下无法继续推进 |

如果 SDK 文档化了等价映射，不需要使用这些精确字符串。

## 4. 必需能力

### 4.1 从 Config 创建

SDK SHOULD 提供一个稳定语义入口，等价于 `from_config(config, runtime_options)`。

该操作 MUST NOT 仅因解析 config 就连接远端 Server 或执行 MCP tools。它 MAY 校验 shape、解析默认值并构建本地 runtime intent。

无效 config MUST 返回公开 validation error，并在可行时包含 field/path 信息。错误中 MUST NOT 泄露 secret values。

### 4.2 Start

`start` 或等价操作初始化服务前所需的本地 runtime 资源：

1. 加载并校验 desired state。
2. 初始化 MCP Server manager intent。
3. 初始化 SKILL registry、blob resolver 和 Desktop/resource tracking。
4. Reconcile 本地可用的 marketplace/plugin/user/MCP source capability。
5. 构建 Agent-facing projection。

`start` MAY 立即或惰性启动 MCP Server processes，但连接后的最终 `client:get_*` 行为 MUST 匹配已加载的 desired state。

### 4.3 Stop

`stop` 或等价操作停止 service activity，但不一定删除 durable desired state：

1. 按 SDK policy 停止或 detach 本地 MCP Server activity。
2. 停止 watchers 和 update emitters。
3. 在 stop 完成后阻止新的 Agent-facing work 被接受。
4. 保留 durable desired state，除非调用方明确要求删除。

### 4.4 Connect And Join Office

`connect` 或等价操作建立协议连接：

1. 除非另有配置，使用 `/smcp` namespace。
2. 发送 URL query `a2c_version`。
3. 发送 `auth.role = "computer"`，并附加调用方提供的非敏感业务 auth fields。
4. 当提供 office config 或调用方要求时，使用 `server:join_office` 加入 Office。

连接失败 MUST 被分类，使调用方能区分 protocol version mismatch、auth failure、network failure 和 join failure。

### 4.5 Disconnect

`disconnect` 或等价操作结束 Socket.IO 连接，但不销毁 durable local config。断开后：

1. Runtime MUST NOT 向之前的 Office 发送 `server:update_*`。
2. Runtime MAY 继续本地管理操作。
3. 后续 reconnect MUST 投影当前 desired state，而不是上一次连接留下的 stale state。

### 4.6 Sync Config

`sync_config(new_config)` 或等价操作把新的 desired state 应用到既有 runtime。

实现 MAY 使用 incremental update、rebuild、restart、lazy apply 或 full reconcile。contract 只要求：

1. 最终 public runtime state 匹配 `new_config`。
2. 已移除或禁用的 capabilities 不再保持可见或可调用。
3. 新启用的 capabilities 在成功 reconcile 后变为可见。
4. 如果已加入 Office，Agent-facing projection 变化会发送对应 `server:update_*`。
5. Partial failure 进入 `degraded` 或返回公开 partial-failure result；它 MUST NOT 暴露歧义能力或被 policy-rejected 的能力。
6. Secret values MUST NOT 出现在 errors、发送给 Agent 的 diagnostics 或 public protocol projection 中。

### 4.7 Shutdown

`shutdown` 或等价操作释放 runtime 资源：

1. 如果已连接，则断开 SMCP Server。
2. 停止 runtime 拥有的 MCP Server activity。
3. 停止 watchers、timers、background tasks 和 update emitters。
4. 释放 runtime 拥有的 blob/spool resources。
5. 在 shutdown 完成后阻止 stale callbacks、`server:update_*` emissions 或迟到的 tool-call ack attempts。

删除 durable config 不属于 shutdown，除非由独立管理操作明确请求。

## 5. Marketplace And Plugin Contract

暴露 marketplace/plugin management 的 SDK SHOULD 对齐以下语义：

1. Marketplace reconcile 默认 additive：声明的 sources 会被 installed/updated/refreshed；未声明但已物化的 sources 不会被删除，直到 explicit prune/gc。
2. Marketplace sync failure 是 degraded：其它 sources 可以继续；如果 failed source 物化失败，其能力不会作为 active 暴露。
3. 为跨 SDK fixture 目的，Plugin id 使用语义形式 `<plugin>@<marketplace>`。SDK MAY 把它包装为 typed IDs。
4. Installing/enabling plugin 会把它的 SKILL、MCP Server、input 和 tool metadata contributions reconcile 到既有 projection surfaces。
5. Disabling/removing plugin 会让它贡献的 capabilities 变为不可见或不可调用。
6. Foreign MCP Server name conflict SHOULD 在挂载 plugin-contributed servers 前被拒绝。Plugin-owned servers MAY 被幂等更新。
7. Plugin-scoped inputs MUST 避免同一 bare input id 在不同 plugin 间泄露值。

## 6. 错误类别

SDK SHOULD 暴露等价的公开错误类别：

| 类别 | 典型触发 | 可重试性 |
|---|---|---|
| `validation` | config shape 非法、plugin id 非法、marketplace name 非法、scope 非法 | 修复 config 后重试 |
| `policy` | Source blocked、permission denied、policy-only field in user scope | policy 变更后重试 |
| `conflict` | Foreign MCP Server name conflict、concurrent writer conflict | 解决冲突后重试 |
| `auth` | SMCP auth failure、source auth failure、MCP upstream authorization failure | credentials/auth flow 完成后重试 |
| `network` | Server unreachable、marketplace fetch failed、transient transport failure | 通常可重试 |
| `protocol_version` | HTTP handshake `4008` | 不改版本则不可重试 |
| `startup` | MCP Server startup failure、dependency missing | 取决于 diagnostic |
| `partial_failure` | Some sources applied, some failed | 重试 failed subset 或 sync |
| `shutdown` | Cleanup failure | 重试 cleanup 或 force stop |

错误 MUST NOT 包含 secret values。管理面错误不会变成 Agent-facing `ErrorPayload`，除非它们发生在既有 `client:*` handler 内；此时适用既有协议错误 shape。

## 7. Client 责任

业务 client 仍负责：

- 管理多个 Computer runtimes。
- 持久化 user/workspace account selection。
- 选择 Server、office 和 user-facing reconnect policy。
- 拥有 product UI state 和 operation audit logs。
- 按产品策略存储 secrets。
- 协调多个 runtimes 的更新。

单个 Computer runtime 仍负责：

- 管理一个 Computer 的 MCP lifecycle。
- 解析本地 inputs 和 secrets。
- 将 tools/resources/Desktop/SKILL/Blob 投影到 Agent-facing protocol。
- 在 shutdown 时释放拥有的 resources。

## 8. 兼容性

兼容性标签：**Runtime-contract**。

SDK 可能需要新增 public API wrappers 或 conformance fixtures，但不需要改变 Agent-facing wire schema。
