# Computer Runtime Contract

本文定义业务 client 可以跨 SDK 依赖的单个 Computer runtime 公共语义。它不是 wire protocol，也不规定 Python、Rust、TypeScript 或其它 SDK 的代码形态。

Runtime contract 的目标是：同一份声明式 `ComputerConfig` 和 `RuntimeOptions` 在不同 SDK 中产生等价 runtime intent，并通过一致的生命周期、错误分类、marketplace/plugin 挂载、`sync_config` final state 和 shutdown 语义交付给业务 client。

## 1. Boundary

Runtime contract owns:

- 从声明式 config 创建一个 runtime Computer。
- 启动、停止、连接、断开、同步配置、关闭一个 runtime Computer。
- 默认值解析、生命周期状态、错误分类和 retryability。
- marketplace / plugin / user / MCP source 能力挂载语义。
- 单个 runtime 与 Agent-facing protocol projection 的一致性。
- 共享 JSON fixture 与生命周期 conformance tests。

Runtime contract does not own:

- 多 Computer 编排、UI 状态、账号选择、Server 选择、office 策略和审计流。
- Python dataclass、Rust builder、TypeScript constructor、trait 名、class 名或 method 名。
- 内部缓存、锁、watcher、目录布局、进程模型、async runtime、CLI UX。

## 2. Core Objects

### 2.1 ComputerConfig

SDKs SHOULD accept a declarative config object with this semantic content:

| Field family | Semantic expectation |
|---|---|
| identity | Computer protocol name and optional local display metadata |
| mcp_servers | MCP Server configs, disabled flags, forbidden tools, tool metadata and transport parameters |
| inputs | Input definitions used to render MCP Server configs locally |
| skills | User DropIn roots or equivalent local SKILL source declarations |
| marketplaces | Known marketplace source declarations and trust/update policy |
| plugins | Installed/enabled plugin declarations and plugin-scoped capability intent |
| settings_policy | Scope merge result or equivalent governance policy |
| connection | Optional default Server URL, namespace, office and auth payload policy |

The config shape may differ by SDK, but shared conformance fixtures MUST be expressible as JSON and map to equivalent runtime intent.

### 2.2 RuntimeOptions

SDKs SHOULD accept runtime options for environment-specific behavior:

| Option family | Semantic expectation |
|---|---|
| home | Optional local Computer home or storage root |
| workdirs | Registered workdirs used for capability discovery |
| secret providers | Local input/secret resolver hooks |
| auth payload provider | Callback or value used to add non-A2C business auth fields |
| network options | Socket.IO path, namespace, transport, timeout and reconnect options |
| blob thresholds | Inline, too-large and chunk-size budgets |
| policy hooks | Local source trust, plugin approval and management authorization hooks |
| diagnostics hooks | Logging, metrics and health observers |

RuntimeOptions MAY choose SDK-specific names and defaults. The final externally visible behavior MUST match the contract.

## 3. Lifecycle States

SDKs SHOULD expose lifecycle state or equivalent public diagnostics with these semantics:

| State | Meaning |
|---|---|
| `created` | Runtime object exists but has not initialized local resources |
| `starting` | Runtime is loading config, resolving local state or starting MCP resources |
| `started` | Local runtime is initialized; it may or may not be connected to SMCP Server |
| `connecting` | Runtime is establishing Socket.IO connection and protocol handshake |
| `connected` | Socket.IO connection is established but Office join may not be complete |
| `joined_office` | Computer has joined an Office and can receive routed `client:*` events |
| `syncing` | Runtime is applying a new config or reconciling desired state |
| `degraded` | Runtime is partially available with public diagnostics |
| `disconnecting` | Runtime is leaving or closing the Socket.IO connection |
| `stopping` | Runtime is stopping local MCP/service activity |
| `stopped` | Runtime has stopped service activity |
| `shutdown` | Runtime has released resources and should not emit stale events |
| `error` | Runtime cannot progress without external action or new config |

SDKs do not need to use these exact strings if they document an equivalent mapping.

## 4. Required Capabilities

### 4.1 Create From Config

SDKs SHOULD provide a stable semantic entry point equivalent to `from_config(config, runtime_options)`.

The operation MUST NOT connect to a remote Server or execute MCP tools merely by parsing config. It MAY validate shape, resolve defaults and construct local runtime intent.

Invalid config MUST return a public validation error with field/path information where practical. It MUST NOT leak secret values in the error.

### 4.2 Start

`start` or equivalent initializes local runtime resources needed before service:

1. Load and validate desired state.
2. Initialize MCP Server manager intent.
3. Initialize SKILL registry, blob resolver and Desktop/resource tracking.
4. Reconcile marketplace/plugin/user/MCP source capability that is available locally.
5. Build Agent-facing projection.

`start` MAY start MCP Server processes immediately or lazily, but final `client:get_*` behavior after connection MUST match the loaded desired state.

### 4.3 Stop

`stop` or equivalent stops service activity without necessarily deleting durable desired state:

1. Stop or detach local MCP Server activity according to SDK policy.
2. Stop watchers and update emitters.
3. Prevent new Agent-facing work from being accepted after stop completes.
4. Preserve durable desired state unless the caller explicitly requests deletion.

### 4.4 Connect And Join Office

`connect` or equivalent establishes the protocol connection:

1. Use `/smcp` namespace unless configured otherwise.
2. Send URL query `a2c_version`.
3. Send `auth.role = "computer"` plus caller-provided non-sensitive business auth fields.
4. Join an Office with `server:join_office` when office config is supplied or when caller requests it.

Connect failure MUST be categorized so callers can distinguish protocol version mismatch, auth failure, network failure and join failure.

### 4.5 Disconnect

`disconnect` or equivalent ends the Socket.IO connection without destroying durable local config. After disconnect:

1. Runtime MUST NOT emit `server:update_*` to the previous Office.
2. Runtime MAY continue local management operations.
3. Subsequent reconnect MUST project current desired state, not stale state from the prior connection.

### 4.6 Sync Config

`sync_config(new_config)` or equivalent applies a new desired state to an existing runtime.

The implementation MAY use incremental update, rebuild, restart, lazy apply or full reconcile. The contract only requires:

1. The final public runtime state matches `new_config`.
2. Removed or disabled capabilities do not remain visible or callable.
3. Newly enabled capabilities become visible after successful reconcile.
4. Agent-facing projection changes emit the corresponding `server:update_*` if joined to an Office.
5. Partial failure enters `degraded` or returns a public partial-failure result; it MUST NOT expose ambiguous or policy-rejected capabilities.
6. Secret values MUST NOT appear in errors, diagnostics sent to Agent, or public protocol projection.

### 4.7 Shutdown

`shutdown` or equivalent releases runtime resources:

1. Disconnect from SMCP Server if connected.
2. Stop MCP Server activity owned by the runtime.
3. Stop watchers, timers, background tasks and update emitters.
4. Release blob/spool resources owned by the runtime.
5. Prevent stale callbacks, `server:update_*` emissions or late tool-call ack attempts after shutdown completes.

Durable config deletion is not part of shutdown unless explicitly requested by a separate management operation.

## 5. Marketplace And Plugin Contract

SDKs that expose marketplace/plugin management SHOULD align on these semantics:

1. Marketplace reconcile is additive by default: declared sources are installed/updated/refreshed; undeclared but materialized sources are not deleted until explicit prune/gc.
2. Marketplace sync failure is degraded: other sources can continue; failed source capabilities are not exposed as active if materialization failed.
3. Plugin id uses the semantic form `<plugin>@<marketplace>` for cross-SDK fixture purposes. SDKs MAY wrap it in typed IDs.
4. Installing/enabling a plugin reconciles its SKILL, MCP Server, input and tool metadata contributions into existing projection surfaces.
5. Disabling/removing a plugin makes its contributed capabilities invisible or non-callable.
6. Foreign MCP Server name conflict SHOULD be rejected before mounting plugin-contributed servers. Plugin-owned servers MAY be updated idempotently.
7. Plugin-scoped inputs MUST avoid leaking values across plugins with the same bare input id.

## 6. Error Categories

SDKs SHOULD expose public error categories equivalent to:

| Category | Typical triggers | Retryability |
|---|---|---|
| `validation` | Invalid config shape, invalid plugin id, invalid marketplace name, invalid scope | Retry after config fix |
| `policy` | Source blocked, permission denied, policy-only field in user scope | Retry after policy change |
| `conflict` | Foreign MCP Server name conflict, concurrent writer conflict | Retry after resolving conflict |
| `auth` | SMCP auth failure, source auth failure, MCP upstream authorization failure | Retry after credentials/auth flow |
| `network` | Server unreachable, marketplace fetch failed, transient transport failure | Usually retryable |
| `protocol_version` | HTTP handshake `4008` | Not retryable without version change |
| `startup` | MCP Server startup failure, dependency missing | Depends on diagnostic |
| `partial_failure` | Some sources applied, some failed | Retry failed subset or sync |
| `shutdown` | Cleanup failure | Retry cleanup or force stop |

Errors MUST NOT include secret values. Management errors do not become Agent-facing `ErrorPayload` unless they occur inside an existing `client:*` handler; in that case the existing protocol error shape applies.

## 7. Client Responsibility

Business clients remain responsible for:

- Managing multiple Computer runtimes.
- Persisting user/workspace account selection.
- Choosing Server, office and user-facing reconnect policy.
- Owning product UI state and operation audit logs.
- Storing secrets according to product policy.
- Coordinating updates across runtimes.

The single Computer runtime remains responsible for:

- Managing one Computer's MCP lifecycle.
- Resolving local inputs and secrets.
- Projecting tools/resources/Desktop/SKILL/Blob to the Agent-facing protocol.
- Releasing owned resources on shutdown.

## 8. Compatibility

Compatibility label: **Runtime-contract**.

SDKs may need new public API wrappers or conformance fixtures, but no Agent-facing wire schema changes are required.
