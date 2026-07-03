# 管理面协议边界

本文定义 Computer Management Plane 与 Agent-facing SMCP 协议面的边界。它不新增远程管理事件，而是规定管理操作完成后，Computer 对 Agent 和 Server 可观察行为必须满足的投影、安全与通知规则。

## 1. 范围

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

## 2. 规范性投影规则

### 2.1 MCP Server 投影

当管理面新增、更新、禁用或移除 MCP Server 后，Computer 的 Agent-facing 投影 MUST 满足：

1. `client:get_config` MUST 返回当前 Agent 可安全观察的 `servers` 与 `inputs` 视图。
2. `client:get_config` MUST NOT 展开 secret 值、`.skillenv` 内容、OAuth token、API key、环境变量实际值或本地凭据文件内容。
3. 禁用或移除的 MCP Server 的工具 MUST NOT 出现在后续 `client:get_tools` 响应中。
4. 禁用或移除的 MCP Server 的工具 MUST NOT 被 `client:tool_call` 成功执行。
5. 管理面使 MCP Server 不可用后，相关 MCP source SKILL MUST 从后续 `client:get_skills` 响应中消失或被排除为不可见孤儿。
6. `client:get_resources` 对不存在的 `mcp_server` MUST 返回 `4014 MCP Server Not Found`；对未声明 `resources` capability 的 server MUST 返回 `4015 MCP Capability Not Supported`。

### 2.2 工具投影

管理面可以配置 disabled server、forbidden tool、alias、default tool metadata 和 per-tool metadata。完成后：

1. Computer MUST 保证 Agent 看到的每个 `SMCPTool.name` 可路由到唯一目标。
2. 同名工具冲突 MUST 通过 alias、禁用、配置拒绝或其它管理面策略解决；Computer MUST NOT 让同一个 `tool_name` 随机路由到不同 MCP Server。
3. forbidden 或 disabled 工具 MUST NOT 出现在可调用工具列表中，也 MUST NOT 被 `client:tool_call` 成功执行。
4. A2C 工具元数据中的复杂结构 MUST 按 [SMCPTool.meta 序列化规范](../data-structures.md#smcptoolmeta-序列化规范) 放入 `meta["a2c_tool_meta"]` JSON 字符串。

### 2.3 SKILL 投影

管理面可以从 user DropIn、marketplace/plugin、MCP `skill://` resource 或其它本地 source 物化 SKILL。完成后：

1. `client:get_skills` MUST 只返回活跃、已物化、可用且未 orphan 的 SKILL。
2. `A2CSkillRef.name`、`source`、`path` 和 `description` MUST 按 [SKILL 数据结构](../data-structures.md#skill-相关结构) 填充。
3. `client:get_skill` MUST 先校验 name lexer；非法 name 返回 `4016`。
4. 合法但未注册、已卸载或已 orphan 的 name MUST 返回 `4014`。
5. `rel_path` MUST 限制在 SKILL 包根内；路径穿越、`.skillenv`、凭据类文件、包内不存在或超过生产者上限 MUST 返回 `4017`。
6. 成功时 `body` 与 `blob_handle` MUST 恰一存在；二进制或过大文本 MUST 转 `client:get_blob`。

### 2.4 Blob 投影

管理面或 SDK 实现 MAY 使用本地缓存、spool、content-addressed store 或 streaming source，但 Agent-facing blob 行为必须保持：

1. `blob_handle` 对 Agent 是不透明能力引用；Agent MUST NOT 解析、拼接、伪造或跨 Computer 复用。
2. Computer 每次处理 `client:get_blob` 时 MUST 重新施加铸造通道的授权与边界校验。
3. Computer MUST 使用资源字节的绝对 `chunk_offset` 切片，返回稳定的 `total_size`、`sha256`、`chunk_offset`、`eof` 和 base64 `blob`。
4. 无效句柄、重施鉴权失败、源消失或范围错误 MUST 返回 `4018`。
5. Computer MUST NOT 把 `client:get_blob` 实现为任意本地文件读取接口。

### 2.5 Desktop 投影

管理面改变 MCP Server、plugin 或 resource source 后，Desktop 投影 MUST 继续满足 [Desktop 桌面系统](../desktop.md)：

1. `client:get_desktop` 未带 `window` 时返回聚合视图；带 `window` 时按完整 URI 字符串精确匹配。
2. Computer MUST 跳过无效 `window://` URI、空内容窗口以及当前无法渲染的纯 Blob 窗口。
3. Computer MUST 使用 Resource `annotations.priority` 与 `_meta.fullscreen` 的协议语义组织结果。
4. 管理面不应把本地路径、安装日志、secret 或管理诊断渲染进 Desktop。

## 3. 通知

当管理面操作导致 Agent-facing projection 变化，且 Computer 已加入 Office 时：

| 投影变化 | Computer SHOULD 发送 | Agent 后续拉取 |
|---|---|---|
| Agent 可见 MCP config 或 inputs 变化 | `server:update_config` | `client:get_config` |
| 工具集合、别名、禁用状态或工具元数据变化 | `server:update_tool_list` | `client:get_tools` |
| `window://` 集合或内容变化 | `server:update_desktop` | `client:get_desktop` |
| SKILL 集合、frontmatter 或可读资源变化 | `server:update_skills` | `client:get_skills` / `client:get_skill` |

Computer MAY 对多次本地变化做 debounce 或 coalesce，但 SHOULD 保证 Agent 最终能通过对应 `client:get_*` 事件拉取到最新投影。

如果 Computer 未连接或尚未加入 Office，管理操作 MUST NOT 产生跨房间可见通知。Computer 可以在本地记录 dirty state，并在加入 Office 后发布；也可以依赖 Agent 的初始拉取。

## 4. Marketplace 与 Plugin 边界

Marketplace 和 plugin 是管理面概念，不是新的 Agent-facing 协议对象。

当 plugin 被安装或启用时，它提供的 managed capability MUST reconcile 到既有协议表面：

| Plugin 贡献 | 投影表面 |
|---|---|
| MCP Server config | `client:get_config`、`client:get_tools`、`client:get_resources`、Desktop |
| SKILL package | `client:get_skills`、`client:get_skill`、`client:get_blob` |
| Tool metadata policy | `client:get_tools` |
| Input definitions | `client:get_config`，且省略 secret 值 |

当 plugin 被禁用或移除时，该 plugin 贡献的所有能力 MUST 通过既有 Agent-facing 协议表面变为不可见或不可调用。

plugin 贡献的 MCP Server 与无关既有 server 发生 name 冲突时，管理面 SHOULD 在投影前拒绝该冲突。即使冲突未被拒绝，最终 Agent-facing 投影仍 MUST NOT 暴露歧义路由。

## 5. Inputs 与 Secrets 边界

Input definitions 和 secret resolution 是 Computer 本地职责。

1. `client:get_config` MAY 暴露 Agent 理解配置所需的 input definitions，但 MUST NOT 暴露已解析的 secret 值。
2. Placeholder rendering、env file loading、command inputs、value cache 和 plugin-scoped input disambiguation 属于管理面/runtime 关注点，不是 Agent 协议字段。
3. `.skillenv`、OAuth tokens、API keys、password values、本地 secret store paths 以及包含凭据的 command output MUST NOT 出现在 Agent-facing responses 或 `ErrorPayload.details` 中。
4. Plugin-scoped inputs MAY 在内部消歧，但最终投影 MUST 避免跨 plugin 值泄露。

## 6. 连接边界

Management APIs 可以提供 `connect`、`disconnect`、`join`、`leave` 或等价能力。wire contract 保持如下：

1. Computer MUST 使用 URL query `a2c_version` 和 `auth.role = "computer"` 连接 `/smcp`。
2. Computer MUST 使用 `server:join_office`，其中 `role = "computer"`，并携带用于 Server 路由的 `name`。
3. Computer MUST 遵守单 Office 绑定和 Server 强制的房间隔离。
4. Management auth payloads MUST NOT 包含 MCP Server credentials、`.skillenv` content 或本地 secret values。

## 7. 安全不变量

Computer Management Plane 是高权限表面。合规 Computer MUST 保持这些不变量：

1. 除非部署方显式构建了独立且已认证的管理表面，否则 Agent 不能使用管理操作。
2. Agent-facing `client:*` events MUST NOT 修改管理面的 desired state；但既有协议事件明确定义的本地状态影响除外，例如工具执行副作用。
3. Management diagnostics MUST NOT 被复制到 Agent-facing responses、tool metadata、Desktop strings、SKILL body、Blob chunks 或 update notifications。
4. 被 policy-rejected、disabled、removed、orphaned 或 invalid 的能力 MUST NOT 作为可用能力暴露。
5. Management cleanup MUST NOT 允许删除或读取 Computer 授权本地边界之外的文件。

## 8. 证据摘要

起草本边界前检查了以下 SDK 路径：

| 主题 | Python SDK 证据 | Rust SDK 证据 | 结论 |
|---|---|---|---|
| Computer runtime event surface | `a2c_smcp/computer/computer.py`、`a2c_smcp/computer/socketio/client.py` | `crates/smcp-computer/src/computer.rs`、`crates/smcp-computer/src/socketio_client.rs` | config/tools/resources/skills/blob/desktop/cancel 的 Agent-facing handler surface 共享 |
| Settings schema and scope | `a2c_smcp/computer/settings/schema.py` | `crates/smcp-computer/src/settings/schema.rs` | tolerant settings model、known fields、plugin id shape 和 policy-only fields 共享 |
| Marketplace reconcile | `a2c_smcp/computer/settings/reconciler.py` | `crates/smcp-computer/src/settings/reconciler.rs` | additive-only reconcile、显式 prune/gc 和 orphan detection 共享 |
| Plugin lifecycle | `a2c_smcp/computer/settings/installer.py` | `crates/smcp-computer/src/settings/installer.rs` | install/enable/disable/uninstall 概念和 foreign MCP name conflict rejection 共享 |
| Inputs | `a2c_smcp/computer/inputs/*` | `crates/smcp-computer/src/inputs/*` | plugin-scoped input disambiguation 和 local resolution boundary 共享 |
| SKILL / Blob / Desktop | `a2c_smcp/computer/skills/*`、`blob/*`、`desktop/*` | `crates/smcp-computer/src/skills/*`、`blob/*`、`desktop/*` | projection behavior 共享；implementation details 不同 |

这些路径只作为证据。它们的 class 名称、trait 形态、锁、store、watcher 和目录布局不是协议要求。

## 9. 兼容性

兼容性标签：**Documentation-only + Tightening + Runtime-contract-adjacent**。

不新增 Agent-facing event 或 schema。Tightening 只适用于安全、投影和歧义规则；这些规则已经是正确互操作所必需的要求。
