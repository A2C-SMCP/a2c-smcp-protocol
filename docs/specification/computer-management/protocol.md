# Management Protocol Boundary

本文定义 Computer Management Plane 与 Agent-facing SMCP 协议面的边界。它不新增远程管理事件，而是规定管理操作完成后，Computer 对 Agent 和 Server 可观察行为必须满足的投影、安全与通知规则。

## 1. Scope

Computer Management Plane 覆盖：

- 从声明式 config 构造一个 runtime Computer 的 desired state。
- 管理 MCP Server config、启停意图、disabled/forbidden 状态和工具元数据。
- 管理 marketplace、plugin、user DropIn 和 MCP resource 贡献的 SKILL。
- 管理 input definitions、secret 引用、本地 value cache 和 plugin-scoped inputs。
- 管理 Computer 与 SMCP Server / Office 的连接生命周期。
- 把本地 desired state reconcile 为 Agent-facing `client:get_*` 结果与 `server:update_*` 通知。

Computer Management Plane 不定义：

- 新的 Agent-facing Socket.IO event。
- 远程管理 RPC 的传输格式、鉴权字段、CLI 命令或 UI 行为。
- 本地 home 目录布局、缓存编码、文件锁、watcher、debounce 时间、进程模型或 async runtime。
- Python、Rust 或 TypeScript 的 class、trait、builder、constructor 或 method 名。

## 2. Normative Projection Rules

### 2.1 MCP Server Projection

当管理面新增、更新、禁用或移除 MCP Server 后，Computer 的 Agent-facing 投影 MUST 满足：

1. `client:get_config` MUST 返回当前 Agent 可安全观察的 `servers` 与 `inputs` 视图。
2. `client:get_config` MUST NOT 展开 secret 值、`.skillenv` 内容、OAuth token、API key、环境变量实际值或本地凭据文件内容。
3. 禁用或移除的 MCP Server 的工具 MUST NOT 出现在后续 `client:get_tools` 响应中。
4. 禁用或移除的 MCP Server 的工具 MUST NOT 被 `client:tool_call` 成功执行。
5. 管理面使 MCP Server 不可用后，相关 MCP source SKILL MUST 从后续 `client:get_skills` 响应中消失或被排除为不可见孤儿。
6. `client:get_resources` 对不存在的 `mcp_server` MUST 返回 `4014 MCP Server Not Found`；对未声明 `resources` capability 的 server MUST 返回 `4015 MCP Capability Not Supported`。

### 2.2 Tool Projection

管理面可以配置 disabled server、forbidden tool、alias、default tool metadata 和 per-tool metadata。完成后：

1. Computer MUST 保证 Agent 看到的每个 `SMCPTool.name` 可路由到唯一目标。
2. 同名工具冲突 MUST 通过 alias、禁用、配置拒绝或其它管理面策略解决；Computer MUST NOT 让同一个 `tool_name` 随机路由到不同 MCP Server。
3. forbidden 或 disabled 工具 MUST NOT 出现在可调用工具列表中，也 MUST NOT 被 `client:tool_call` 成功执行。
4. A2C 工具元数据中的复杂结构 MUST 按 [SMCPTool.meta 序列化规范](../data-structures.md#smcptoolmeta-序列化规范) 放入 `meta["a2c_tool_meta"]` JSON 字符串。

### 2.3 SKILL Projection

管理面可以从 user DropIn、marketplace/plugin、MCP `skill://` resource 或其它本地 source 物化 SKILL。完成后：

1. `client:get_skills` MUST 只返回活跃、已物化、可用且未 orphan 的 SKILL。
2. `A2CSkillRef.name`、`source`、`path` 和 `description` MUST 按 [SKILL 数据结构](../data-structures.md#skill-相关结构) 填充。
3. `client:get_skill` MUST 先校验 name lexer；非法 name 返回 `4016`。
4. 合法但未注册、已卸载或已 orphan 的 name MUST 返回 `4014`。
5. `rel_path` MUST 限制在 SKILL 包根内；路径穿越、`.skillenv`、凭据类文件、包内不存在或超过生产者上限 MUST 返回 `4017`。
6. 成功时 `body` 与 `blob_handle` MUST 恰一存在；二进制或过大文本 MUST 转 `client:get_blob`。

### 2.4 Blob Projection

管理面或 SDK 实现 MAY 使用本地缓存、spool、content-addressed store 或 streaming source，但 Agent-facing blob 行为必须保持：

1. `blob_handle` 对 Agent 是不透明能力引用；Agent MUST NOT 解析、拼接、伪造或跨 Computer 复用。
2. Computer 每次处理 `client:get_blob` 时 MUST 重新施加铸造通道的授权与边界校验。
3. Computer MUST 使用资源字节的绝对 `chunk_offset` 切片，返回稳定的 `total_size`、`sha256`、`chunk_offset`、`eof` 和 base64 `blob`。
4. 无效句柄、重施鉴权失败、源消失或范围错误 MUST 返回 `4018`。
5. Computer MUST NOT 把 `client:get_blob` 实现为任意本地文件读取接口。

### 2.5 Desktop Projection

管理面改变 MCP Server、plugin 或 resource source 后，Desktop 投影 MUST 继续满足 [Desktop 桌面系统](../desktop.md)：

1. `client:get_desktop` 未带 `window` 时返回聚合视图；带 `window` 时按完整 URI 字符串精确匹配。
2. Computer MUST 跳过无效 `window://` URI、空内容窗口以及当前无法渲染的纯 Blob 窗口。
3. Computer MUST 使用 Resource `annotations.priority` 与 `_meta.fullscreen` 的协议语义组织结果。
4. 管理面不应把本地路径、安装日志、secret 或管理诊断渲染进 Desktop。

## 3. Notifications

当管理面操作导致 Agent-facing projection 变化，且 Computer 已加入 Office 时：

| Projection 变化 | Computer SHOULD emit | Agent 后续拉取 |
|---|---|---|
| Agent 可见 MCP config 或 inputs 变化 | `server:update_config` | `client:get_config` |
| 工具集合、别名、禁用状态或工具元数据变化 | `server:update_tool_list` | `client:get_tools` |
| `window://` 集合或内容变化 | `server:update_desktop` | `client:get_desktop` |
| SKILL 集合、frontmatter 或可读资源变化 | `server:update_skills` | `client:get_skills` / `client:get_skill` |

Computer MAY debounce or coalesce multiple local changes, but SHOULD guarantee that Agent can eventually fetch the latest projection via the corresponding `client:get_*` event.

If the Computer is not connected or has not joined an Office, management operations MUST NOT create cross-room visible notifications. The Computer can record dirty state locally and publish after it joins, or rely on Agent initial fetch.

## 4. Marketplace And Plugin Boundary

Marketplace and plugin are management concepts. They are not new Agent-facing protocol objects.

When a plugin is installed or enabled, its managed capability MUST be reconciled into existing protocol surfaces:

| Plugin contribution | Projection surface |
|---|---|
| MCP Server config | `client:get_config`, `client:get_tools`, `client:get_resources`, Desktop |
| SKILL package | `client:get_skills`, `client:get_skill`, `client:get_blob` |
| Tool metadata policy | `client:get_tools` |
| Input definitions | `client:get_config` with secret values omitted |

When a plugin is disabled or removed, all capabilities contributed by that plugin MUST become invisible or non-callable through existing Agent-facing protocol surfaces.

MCP Server name conflict between plugin-contributed server and an unrelated existing server SHOULD be rejected by the management plane before projection. If conflict is not rejected, the final Agent-facing projection still MUST NOT expose ambiguous routing.

## 5. Inputs And Secrets Boundary

Input definitions and secret resolution are local Computer responsibilities.

1. `client:get_config` MAY expose input definitions needed for Agent understanding, but MUST NOT expose resolved secret values.
2. Placeholder rendering, env file loading, command inputs, value cache and plugin-scoped input disambiguation are management/runtime concerns, not Agent protocol fields.
3. `.skillenv`, OAuth tokens, API keys, password values, local secret store paths and command output containing credentials MUST NOT appear in Agent-facing responses or `ErrorPayload.details`.
4. Plugin-scoped inputs MAY be disambiguated internally, but the final projection MUST avoid cross-plugin value leakage.

## 6. Connection Boundary

Management APIs may offer `connect`, `disconnect`, `join`, `leave` or equivalent capabilities. The wire contract remains:

1. Computer MUST connect to `/smcp` with URL query `a2c_version` and `auth.role = "computer"`.
2. Computer MUST use `server:join_office` with `role = "computer"` and a `name` used for Server routing.
3. Computer MUST respect single-Office binding and Server-enforced room isolation.
4. Management auth payloads MUST NOT include MCP Server credentials, `.skillenv` content or local secret values.

## 7. Security Invariants

Computer Management Plane is high-privilege. A compliant Computer MUST preserve these invariants:

1. Agent cannot use management operations unless the deployment explicitly builds a separate authenticated management surface.
2. Agent-facing `client:*` events MUST NOT mutate management desired state except where an existing protocol event explicitly defines local state effects, such as tool execution side effects.
3. Management diagnostics MUST NOT be copied into Agent-facing responses, tool metadata, Desktop strings, SKILL body, Blob chunks or update notifications.
4. Policy-rejected, disabled, removed, orphaned or invalid capabilities MUST NOT be exposed as available capabilities.
5. Management cleanup MUST NOT allow deleting or reading files outside the Computer's authorized local boundary.

## 8. Evidence Summary

The following SDK paths were checked before drafting this boundary:

| Topic | Python SDK evidence | Rust SDK evidence | Conclusion |
|---|---|---|---|
| Computer runtime event surface | `a2c_smcp/computer/computer.py`, `a2c_smcp/computer/socketio/client.py` | `crates/smcp-computer/src/computer.rs`, `crates/smcp-computer/src/socketio_client.rs` | Shared Agent-facing handler surface for config/tools/resources/skills/blob/desktop/cancel |
| Settings schema and scope | `a2c_smcp/computer/settings/schema.py` | `crates/smcp-computer/src/settings/schema.rs` | Shared tolerant settings model, known fields, plugin id shape and policy-only fields |
| Marketplace reconcile | `a2c_smcp/computer/settings/reconciler.py` | `crates/smcp-computer/src/settings/reconciler.rs` | Shared additive-only reconcile, explicit prune/gc, orphan detection |
| Plugin lifecycle | `a2c_smcp/computer/settings/installer.py` | `crates/smcp-computer/src/settings/installer.rs` | Shared install/enable/disable/uninstall concepts and foreign MCP name conflict rejection |
| Inputs | `a2c_smcp/computer/inputs/*` | `crates/smcp-computer/src/inputs/*` | Shared plugin-scoped input disambiguation and local resolution boundary |
| SKILL / Blob / Desktop | `a2c_smcp/computer/skills/*`, `blob/*`, `desktop/*` | `crates/smcp-computer/src/skills/*`, `blob/*`, `desktop/*` | Shared projection behavior; implementation details differ |

These paths are evidence only. Their class names, trait shapes, locks, stores, watchers and directory layouts are not protocol requirements.

## 9. Compatibility

Compatibility label: **Documentation-only + Tightening + Runtime-contract-adjacent**.

No Agent-facing event or schema is added. Tightening applies only to security, projection and ambiguity rules already required for correct interoperability.
