# SDK API 指南

本文档为非规范性内容。它描述实现 [Computer Runtime Contract](runtime-contract.md) 时推荐的 SDK API 能力，不规定语言专属的 class、trait、builder、constructor 或 async runtime 形态。

## 1. 稳定能力族

鼓励 SDK 暴露以下能力族的公共入口：

| 能力族 | 稳定语义预期 |
|---|---|
| create from config | 从声明式 config 和 runtime options 创建一个 runtime Computer |
| start / stop | 初始化和停止本地 runtime service activity |
| connect / disconnect | 建立和结束 SMCP connection，且不销毁 durable config |
| join / leave office | 当未折叠进 connect/disconnect 时，加入或离开 Office |
| sync config | 应用新 config，使最终 public runtime behavior 与其匹配 |
| query projection | 返回 SDK-visible tools、config、resources、Desktop 和 SKILL 视图，且与协议投影一致 |
| plugin lifecycle | install、enable、disable 和 uninstall plugin-contributed capabilities |
| marketplace lifecycle | add、sync/refresh、list 和 prune marketplace sources |
| input values | resolve、set、clear 和 inspect input values，且不向 Agent 暴露 secrets |
| diagnostics | 返回 lifecycle state、degraded components、validation errors 和 last failures |
| shutdown | 释放 resources，并阻止 stale callbacks/events |

具体名称由各 SDK 自行决定。例如，一个 SDK 可以暴露 builder，另一个可以暴露 factory，第三个可以使用 async constructor。Conformance 以行为为准。

## 2. API 形态建议原则

鼓励 SDK：

1. 将 config parsing 与 side effects 分离。从 config 创建 runtime 不应连接 Server 或执行 tools。
2. 让生命周期操作显式，并在可行时保持幂等。
3. 返回公开 lifecycle state 和 diagnostics，而不是要求调用方检查 logs 或 private fields。
4. 区分 `disconnect`、`stop` 和 `shutdown`。
5. 提供单一 `sync_config` 语义操作，即使实现内部会重建 runtime。
6. 提供与 [Runtime Contract §6](runtime-contract.md#6-错误类别) 对齐的 typed 或 structured error categories。
7. 保持 management diagnostics 与 Agent-facing protocol payloads 隔离。
8. 允许调用方注入业务 auth fields，但不要把 secrets 放入 `a2c_version`、`role`、update notifications 或 Agent-visible config。

## 3. Config 与默认值

SDK 可以使用语言原生类型，但应支持用于 conformance 的共享 JSON fixtures。

推荐默认行为：

| 区域 | 指南 |
|---|---|
| namespace | 默认使用 `/smcp` |
| protocol version | 在 URL query 中使用 SDK 声明的 A2C-SMCP protocol version |
| auth role | `role` 经 `server:join_office`（`EnterOfficeReq.role`）声明；connection `auth` 仅承载业务鉴权（如 token），不含 `role` |
| auto connect | 文档化 start 是否自动 connect；对嵌入方优先推荐显式 connect |
| auto reconnect | 如果支持，应使行为可配置且可观察 |
| disabled servers | 保留 config，但从 Agent-facing projection 中排除能力 |
| forbidden tools | 从 tools 中排除，并拒绝成功执行 |
| marketplace reconcile | 优先采用 additive-only startup reconcile 和 explicit prune/gc |
| plugin conflict | 挂载前拒绝 foreign MCP Server name conflicts |
| secret values | 仅本地解析，绝不放入 Agent-facing projection |

## 4. Lifecycle API 指南

### 4.1 Create

SDK 可以提供任意等价入口：

```
runtime = create_computer(config, runtime_options)
```

该操作应校验 shape 并解析默认值，但避免 network 和 MCP process side effects。

### 4.2 Start

`start` 应初始化本地 resources、registries、blob resolvers、watchers 和 MCP manager intent。如果 start 会立即启动 MCP Servers，SDK 应文档化该 policy，并以 public diagnostics 暴露 startup failures。

### 4.3 Connect

`connect` 应接收 Server URL 和可选 connection options。SDK 应让最终 handshake 足够可检查，以便测试验证：

- `a2c_version` 位于 URL query 中。
- 连接 `auth` 不含 `role`（角色经 `server:join_office` 声明）。
- caller-supplied auth payload 已包含，且不会泄露 MCP credentials。
- 配置后会发送 `server:join_office`，其中 `role = "computer"`。

### 4.4 Sync Config

SDK 应暴露一个应用新 desired config 的操作。它可以实现为：

- incremental update；
- diff-and-apply；
- 在稳定 identity 背后 full rebuild；
- 保持 projection 的 stop/start。

SDK 应文档化 sync 期间 in-flight tool calls 是继续、被取消，还是允许完成。无论实现方式如何，最终 projection 必须匹配新 config。

### 4.5 Shutdown

SDK 应提供一个终止性的 cleanup 操作。完成后：

- 不应再发送 update notification；
- watcher 不应调用 stale callbacks；
- 旧 Socket.IO client 不应 ack 新请求；
- owned MCP server resources 应按文档化 policy 被停止或 detach。

## 5. Plugin 与 Marketplace API 指南

鼓励 SDK 把 plugin 和 marketplace 操作暴露为 management APIs，而不是 Agent-facing protocol events。

推荐 plugin operations：

| 操作 | 指南 |
|---|---|
| install | 物化 plugin、写 `installedPlugins` 意图、校验 manifest、预检 MCP name conflicts；**MUST NOT 激活**（SKILL/MCP/input contributions 待 enable 才注册） |
| enable | 标记 plugin enabled（写 `enabledPlugins=true`）并 reconcile contributions（skills 与 bundled server 原子一并） |
| disable | 标记 plugin disabled，并使 contributions 不可见/不可调用 |
| uninstall | 移除 plugin records 并 teardown owned contributions，除非调用方选择 keep-server policy |
| info/list | 仅向 trusted caller 返回 management diagnostics 和 provenance |

推荐 marketplace operations：

| 操作 | 指南 |
|---|---|
| add | 在 trust/policy approval 后添加 source declaration |
| sync/refresh | fetch/update declared sources，并注册 enabled plugin SKILLs |
| list | 向 trusted caller 返回 source status 和 diagnostics |
| prune | 在调用方确认后显式移除 orphan materialization |

SDK 可以在非 live context 中支持 ledger-only operations，但应文档化：Agent-facing projection changes 需要 live runtime reconcile。

## 6. Inputs 与 Secret 指南

鼓励 SDK：

1. 将 input definitions 与 resolved values 分离。
2. 支持 plugin-scoped input disambiguation，避免相同 bare id 冲突。
3. 避免记录 resolved secret values。
4. 为缺失 input values 暴露 public diagnostics，但不包含实际 secrets。
5. 将 `.skillenv` 和本地 secret files 视为 local-only；绝不把其内容放入 `client:get_skill`、`client:get_blob`、`client:get_config` 或 tool metadata。

## 7. 测试指南

SDK 应同时维护 protocol conformance tests 和 runtime contract tests：

| 测试类别 | 验证内容 |
|---|---|
| wire conformance | `client:*` response shape、flat `ErrorPayload`、update notifications、room behavior |
| runtime conformance | lifecycle state transitions、`sync_config`、plugin/marketplace semantics、shutdown cleanup |
| projection conformance | management operations 后最终 `get_config`/`get_tools`/`get_skills`/`get_desktop` 视图 |
| security conformance | 无 secret/path leakage、sandbox boundaries、blob handle opacity |
| cross-SDK fixture conformance | Python/Rust/TypeScript 将同一 JSON fixture 解析为等价 runtime intent |

共享 checklist 见 [Conformance Tests](conformance-tests.md)。

## 8. 迁移指南

鼓励将本 runtime contract 加入既有 API 的 SDK：

1. 保持既有 constructors/builders 作为 compatibility wrappers 继续工作。
2. 在改变 CLI UX 前，先加入共享 fixture parsing。
3. 引入 lifecycle state diagnostics，同时不改变 Agent-facing wire behavior。
4. 在重构 internals 前，为当前行为补充 conformance tests。
5. 保持 marketplace/plugin management APIs 明确为 trusted-local。

## 9. 非目标

本指南不标准化：

- 必需的 `Computer` class 名；
- 精确的 builder/factory signatures；
- 本地 home layout；
- settings file names；
- watcher implementation；
- process supervision model；
- retry scheduler；
- CLI commands；
- UI flows；
- 运行期命令式 MCP Server CRUD（对非-bundled server 的 add/update/remove）是落盘为 durable 声明意图（重启存活）还是仅内存生效（持久化留给 host 编辑声明文件）——属管理面（CLI/桌面客户端）与内核间的本地约定（详见 runtime-contract §2.3）。
