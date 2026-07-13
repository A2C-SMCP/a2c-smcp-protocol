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
| plugin_installation | `installedPlugins`：全局安装意图（已安装 `<plugin>@<marketplace>` 集合）；install 写此集且**不激活**，见 §2.3 / §2.4 |
| plugin_enablement | `enabledPlugins`：per-scope 启用意图（`<plugin>@<marketplace>` → bool）；仅 `true` 激活，absent/`false`=本 scope 不活跃；与 installation 正交，见 §2.4 |
| settings_policy | Scope merge result 或等价治理策略 |
| connection | 可选默认 Server URL、namespace、office 和 auth payload policy |

不同 SDK 的 config shape 可以不同，但共享 conformance fixtures MUST 能表达为 JSON，并映射为等价 runtime intent。

> **Installation 与 enablement 是两个独立状态、独立生命周期。** Installation 是**全局一次**的安装事实（`installedPlugins`）；enablement 是 **per-scope** 的启用意图（`enabledPlugins`）。SDK MUST NOT 用单一开关同时表达二者——否则一个 scope 的启用会泄漏到其它 scope。尤其：**`install` MUST NOT 激活**（不写 `enabledPlugins`、不进投影），`enable` 才激活；完整状态机见 §2.4。

### 2.2 RuntimeOptions

SDK SHOULD 接受 runtime options，用于表达环境相关行为：

| 选项族 | 稳定语义预期 |
|---|---|
| home | 可选本地 Computer home 或 storage root |
| secret providers | 本地 input/secret resolver hooks |
| auth payload provider | 用于添加非 A2C 业务 auth fields 的 callback 或 value |
| network options | Socket.IO path、namespace、transport、timeout 和 reconnect options |
| blob thresholds | inline、too-large 和 chunk-size budgets |
| policy hooks | 本地 source trust、plugin approval 和 management authorization hooks |
| diagnostics hooks | logging、metrics 和 health observers |

RuntimeOptions MAY 使用 SDK-specific 名称和默认值。最终外部可见行为 MUST 符合本 contract。

### 2.3 状态权威与资产分档

**权威方向 MUST 为 意图 → 派生态，不可逆。** 声明式意图是唯一权威写入入口，含：`installedPlugins`（全局安装意图）、`enabledPlugins`（per-scope 启用意图）、marketplace declarations，以及 `ComputerConfig` 其余声明字段。任何命令式管理操作 MUST 先写对应声明式意图（config-first）：`install` 写 `installedPlugins`、`enable`/`disable` 写 `enabledPlugins`、`add-marketplace` 写 marketplaces；锁 / 物化账本 / 克隆缓存 / 活跃集均为其下游派生物。派生态 MUST 仅由 reconcile 从意图重建，MUST NOT 被直接编辑、也 MUST NOT 作为独立输入参与决策；因此运行时无需为“中间层突变”编写应对逻辑。

> **反模式（rust-sdk#96 根因）**：把能力归属 / 活跃集只持在运行期内存、无法从持久化意图重建，重启即丢。根治是 boot 从持久化意图 reconcile（§4.8），而**非**让 `install` 去写 `enabledPlugins`——`install` 本就不表达启用意图（见 §2.4）。SDK MUST NOT 让任何 boot 依赖的状态只存在于内存。

分层深度 MUST 按资产是否有远端 fetch 步骤而定：

| 资产类别 | 分层 |
|---|---|
| Fetch 资产（marketplace / plugin） | 意图 → 物化账本（派生缓存，记 resolved 版本/位置）→ 克隆缓存 → 活跃集 |
| 纯声明资产（MCP Server 定义、本地 DropIn SKILL） | 意图 → 活跃集 |

SDK MUST NOT 为纯声明资产引入锁或物化目录。物化账本（若实现保留，如 `installed_plugins.json`）MUST 是可从 `installedPlugins` 意图重建的派生缓存，MUST NOT 手编、MUST NOT 提升为权威。

> **命令式 runtime MCP Server CRUD 的持久化语义（deliberately unspecified）**：上文“声明式意图 MUST 持久化、boot 从持久化意图 reconcile”的权威对象是 **plugin / marketplace 声明意图**（`installedPlugins` / `enabledPlugins` / marketplaces）——因为 boot reconcile 的正确性依赖它（§4.8，rust-sdk#96）。它**不**延伸到对**非-bundled MCP Server 的运行期命令式 add / update / remove**：该操作是 Computer 管理面（CLI / 桌面客户端）与内核之间的本地约定，其结果是**落盘为 durable 声明意图（重启存活）**还是**仅内存生效（持久化留给 host 编辑声明文件）**，协议**刻意不作规范**（落在 §3「本地 API / 文件布局 / 进程模型」与 sdk-api-guidance §9 非目标之内）。两种选择都与 config-first 自洽：boot 只从**已持久化**的声明意图 reconcile，未被 durable 声明的运行期临时增量在重启后消失，本就是 config-first 的应有之义，而非上文反模式（后者约束的是 boot 依赖的**能力归属 / 活跃集**只存内存）。SDK MAY 提供「transient / mount」与「declare-durable」两条显式路径；选择与默认交由 SDK，durable 变体 MUST 写入**调用方拥有的位置**（协议不规定文件名 / 布局）。

> **物化账本（materialization ledger，如 `installed_plugins.json`）**：reconcile 从 `installedPlugins` 意图派生出的、机器本地的物化记录，登记 resolved 身份（version / commitSha）、落地位置（installPath）与能力归属（bundled server 属于哪个 plugin）。它只记“已物化成什么”、不记“应该装什么”（后者由 `installedPlugins` 承载）——因此是可弃、可重建的**描述性索引**，不是权威、不是复现锁。判据：**删除它无损**——boot 可从 `installedPlugins` 重新 clone / 解析重建；缺失只是下次 boot 重新物化。安装集本身不丢，因为它在 `installedPlugins`，不在账本。

### 2.4 Plugin 生命周期（install ⊥ enable）

Plugin 有两个正交、独立生命周期的状态维度：**是否安装**（全局，`installedPlugins`）与**本 scope 是否启用**（per-scope，`enabledPlugins`）。二者组合出三个可分别停留的静止态：

| 状态 | `installedPlugins` | `enabledPlugins`（本 scope 合并后） | 投影（skills / bundled MCP server） |
|---|---|---|---|
| `available` | 不含 | —— | 不出现 |
| `installed_disabled` | 含 | absent 或 `false` | **不出现**（已安装但未启用，惰性静止） |
| `installed_enabled` | 含 | `true` | 出现（skills 与 bundled server **一并**活跃） |

`enabledPlugins[<plugin>@<marketplace>]` 三态（用于 scope 合并 user < project < local）：absent = 本 scope 无意见、继承上层（无任何 scope 置 `true` 即不激活）；`true` = 本 scope 启用（激活）；`false` = 本 scope 显式禁用（覆盖上层 `true`）。

> **默认不激活。** 仅被 `install` 的 plugin，在任何 scope 未显式 `true` 前处于 `installed_disabled`——skills 不进 `client:get_skills`、bundled MCP server 不挂。这是相对 v0.2.x「装即活跃」的**破坏性行为变更**，迁移见 [v0.3.0 迁移指南](../../migrations/v0.3.0-plugin-install-enable-separation.md)。

状态迁移 MUST 遵循下表；每个命令式操作 MUST 先写声明式意图（config-first，见 §2.3）：

| 操作 | 意图写入 | 物化 / 投影副作用 | 结果态 |
|---|---|---|---|
| `install` | `installedPlugins` 增 | 物化（clone / 账本）、校验 manifest、预检 foreign MCP name 冲突；**MUST NOT 激活**、MUST NOT 写 `enabledPlugins` | `installed_disabled` |
| `enable` | `enabledPlugins[scope] = true` | 把 skills 与 bundled MCP server **原子**并入投影（见下）；失败 MUST 回滚到 `installed_disabled` | `installed_enabled` |
| `disable` | `enabledPlugins[scope] = false` | 从投影移除其贡献；保留 `installedPlugins` 与物化 | `installed_disabled` |
| `uninstall` | `installedPlugins` 删、清其 `enabledPlugins` 条目 | teardown 物化与 owned server（除非 keep-server policy） | `available` |

> **enable 原子性（消除“半态”）。** `enable` MUST 把该 plugin 的 skills 与 bundled MCP server **条目**作为整体一并纳入投影。被禁止的“半态”锚定在**投影面不一致**——skill 已在 `client:get_skills`、而 bundled server 条目缺席于 config/tool 投影（此即 rust-sdk#102）。在 client-owns-MCP-config 下，把 bundled server 记为 **enabled-可查询条目**即已满足原子性——其**进程拉起**是客户端职责（见 §4.8 边界，不算半态），skills 照常一并投影、无需等待其就绪。仅当 server 连投影条目都无法建立（manifest / 物化失败）时，才整体保持 `installed_disabled` 并给出公开诊断。

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
3. 连接握手 `auth` 仅承载调用方提供的非敏感业务 auth fields（不含 `role`）。
4. 当提供 office config 或调用方要求时，使用 `server:join_office`（`role = "computer"`，角色即在此声明）加入 Office。

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

### 4.8 Boot 治理恢复（Governance Recovery）

从既有 `home` 重建 runtime（进程重启或以相同 `home` 重新构造）时：

1. Boot MUST 以持久化声明式意图为权威重建派生态与活跃集：安装集取自 `installedPlugins`，**活跃集 = 已安装 ∧ 本 scope 启用**（`enabledPlugins` 合并后为 `true`）；`installed_disabled`（已装未启用）MUST 恢复为惰性、不进投影。`start` 的 reconcile（§4.2 第 4 步）MUST 覆盖此恢复。
2. 重建后的 Agent-facing projection MUST 完整包含 enabled plugin 贡献的 bundled MCP Server、bundled SKILL 及由其派生的 MCP-source SKILL，且 MUST NOT 依赖任何调用方持有的内存归属表（in-memory ownership map）。
3. 能力归属元数据（source / marketplace / plugin id 等）MUST 为 boot 的纯函数输出（意图 + resolved location + manifest 重新推导），每次 boot 可复现。
4. Boot reconcile MUST 幂等且 additive-only；删除 MUST 走独立显式路径（prune / gc），MUST NOT 作为 reconcile 的副作用。
5. settings / plugin-marketplace / MCP 三条 reconcile pipeline MAY 各自独立执行；本 contract 不要求把它们合并为单一 reconcile。

> **归属恢复 vs 进程拉起（client-owns-MCP-config 边界）**：上文“完整包含 bundled MCP Server”约束的是**归属与身份**——重建后它 MUST 可作为纯函数从意图 + 账本推导（§4.8.2 / §4.8.3），使调用方无需内存 ownership map。但 bundled MCP server 的**进程拉起 / 物化**MAY 需要调用方提供物化 hooks：当 SDK 约定 MCP server 物化归客户端所有（client owns MCP config）时，SDK MUST 使 enabled bundled server **可查询**（供客户端据此物化，或经治理恢复接口显式拉起），但 MAY 不在 boot 内直接启动其进程。此边界 MUST NOT 退化为“调用方凭内存 map 猜归属”。

### 4.9 物化账本地位与运行期稳定性

本 contract 不要求存在 lock 或物化账本文件。复现性 MUST 来自持久化的声明式意图 + reconcile 重解析（`latest-compatible`）：相同意图在同一或不同机器上重建，MUST 产出等价活跃集（marketplace 按声明 ref 解析当前条目，允许上游漂移）。

1. 若实现保留物化账本，它 MUST 只由 reconcile 从 `installedPlugins` 意图写入，MUST NOT 被直接编辑，MUST NOT 作为权威来源；它是可弃、可 GC、可从 `installedPlugins` 重建的派生缓存。
2. committed pin-lock（记录 `commitSha` / `integrity` 并令 boot 优先按锁复现）是可选、非必需的更强复现扩展；实现 MAY 提供，但 MUST NOT 以派生缓存冒充可复现 lock。
3. 运行期稳定：会话内派生态快照 SHOULD 冻结；后台或磁盘侧变更 MUST NOT 在运行中打乱已投影的 Agent-facing 状态，而是作为 pending 差异留到下次 boot 吸收。此保证“改配置后再启动”确定、“反复重启”结果一致。

## 5. Marketplace And Plugin Contract

暴露 marketplace/plugin management 的 SDK SHOULD 对齐以下语义：

1. Marketplace reconcile 默认 additive：声明的 sources 会被 installed/updated/refreshed；未声明但已物化的 sources 不会被删除，直到 explicit prune/gc。
2. Marketplace sync failure 是 degraded：其它 sources 可以继续；如果 failed source 物化失败，其能力不会作为 active 暴露。
3. 为跨 SDK fixture 目的，Plugin id 使用语义形式 `<plugin>@<marketplace>`。SDK MAY 把它包装为 typed IDs。
4. **Enabling** plugin 会把它的 SKILL、MCP Server、input 和 tool metadata contributions reconcile 到既有 projection surfaces（skills 与 bundled server 原子一并，见 §2.4）。**Installing** 只物化并写 `installedPlugins`，MUST NOT 进入 projection。
5. Disabling/removing plugin 会让它贡献的 capabilities 变为不可见或不可调用。
6. Foreign MCP Server name conflict SHOULD 在挂载 plugin-contributed servers 前被拒绝。Plugin-owned servers MAY 被幂等更新。
7. Plugin-scoped inputs MUST 避免同一 bare input id 在不同 plugin 间泄露值。
8. 安装路径 MUST NOT 作为权威状态。MUST 存在纯函数 `(marketplace, plugin, version) → path`；持久化路径仅为提示，boot MUST 重新校验，失效即重算（worktree / seed 场景 MUST NOT 信任存储的 install location）。
9. 声明（可提交）与凭据（机器本地）MUST 使用不同持久化契约：secret / OAuth token MUST 存于 keychain 或等价机器本地存储，MUST NOT 落入任何可提交的声明文件。
10. MCP Server 启停有两套正交开关，MUST 分清并分别应用：project-scope 声明 server 的信任门（`enabledMcpjsonServers` / `disabledMcpjsonServers` / `enableAllProjectMcpServers`）与通用禁用开关（按命名空间键，对 plugin bundled server 亦生效）。plugin bundled server 的启停 MUST NOT 走 project 信任门。

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
