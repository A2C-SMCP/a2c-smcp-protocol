# Tool Exposure Management

本文定义管理面如何控制 MCP 工具对 Agent 是否可见、是否可调用以及如何命名。它不管理 MCP Server 进程本身。

## 1. 管理范围

本模块管理：

- 管理面工具身份：`server_name + original_tool_name`。
- Agent-facing 工具名唯一性。
- alias、disabled、forbidden、tool metadata。
- 重名工具冲突处理。
- 工具曝光变化到 `client:get_tools` 与 `client:tool_call` 的投影。
- 来自 user / plugin / organization policy 等 source 的 tool policy 收敛。

本模块不管理：

- MCP Server 启停，见 [MCP Server](mcp-server.md)。
- source provenance 与冲突通用规则，见 [Capability Sources](capability-sources.md)。
- 工具执行的取消、超时和二进制结果旁路，见 [Computer 侧协议框架](../computer.md)。

## 2. Tool Identity

管理面 SHOULD 使用 `{server_name, original_tool_name}` 作为稳定工具身份。Agent-facing `SMCPTool.name` 是路由用可见名，MUST 能唯一定位一个 enabled 且未 forbidden 的底层工具。

## 3. Exposure State

| State | 含义 | `client:get_tools` | `client:tool_call` |
|---|---|---|---|
| `exposed` | Agent 可见且可调用 | 返回 | 可成功路由 |
| `disabled` | 管理面禁用 | 不返回 | MUST NOT 成功执行 |
| `forbidden` | 策略强制禁止 | 不返回 | MUST NOT 成功执行 |
| `conflicted` | 命名冲突未解决 | 不应作为可调用工具返回 | MUST NOT 随机路由 |
| `unavailable` | 底层 Server 不可用 | SHOULD 不返回，或返回时必须反映不可用策略 | MUST NOT 假装成功 |

`disabled` 通常是用户或配置选择；`forbidden` 是策略边界。两者都要求 Agent 不可成功调用。

`client:tool_call` 的失败形状仍以 [Computer 侧协议框架 §工具执行、取消与二进制结果](../computer.md#5-工具执行取消与二进制结果) 为准：当请求命中 disabled、forbidden、conflicted 或 unavailable 工具时，Computer MUST NOT execute the underlying MCP tool and MUST return an MCP `CallToolResult` with `isError=true` if the request reaches the Computer handler. Computer MUST NOT return management-plane diagnostics, local policy documents, stack traces, install paths or secret values in the tool error text or `meta`.

If routing fails before the request reaches the Computer handler, Server MAY return the existing flat `ErrorPayload` for routing/isolation failure. This does not create a new management-plane error shape for `client:tool_call`.

## 4. Alias 与重名冲突

如果多个 MCP Server 暴露同名工具，Computer MUST 保证 Agent-facing 工具名唯一可路由。管理面可以通过以下策略之一解决：

- 显式 alias。
- 自动命名空间化。
- 禁用冲突工具。
- 拒绝该配置并返回管理面 conflict 错误。

协议不规定 alias 的 UI 或本地存储。若 alias 进入 Agent-facing 元数据，MUST 使用现有 `SMCPTool.meta["a2c_tool_meta"]` JSON 字符串规则。

Alias affects routing, not only display. If Computer exposes an alias as `SMCPTool.name`, subsequent `client:tool_call.tool_name` using that alias MUST route to exactly one enabled, non-forbidden underlying tool. The original tool name MAY be hidden from `client:get_tools`; if hidden, calling the original name MUST NOT bypass the alias/forbidden policy.

If a forbidden policy names either the original tool name or its Agent-facing alias, Computer MUST suppress every Agent-facing route for that tool unless a documented deterministic policy explicitly scopes the rule to a different identity. The policy result MUST be visible as absence from `client:get_tools` and non-success from `client:tool_call`.

## 5. Tool Metadata

管理面 MAY 设置 tags、auto_apply、ret_object_mapper 等 A2C 元数据。Computer 投影到 `SMCPTool.meta` 时 MUST 遵守 [SMCPTool.meta 序列化规范](../data-structures.md#smcptoolmeta-序列化规范)。

元数据变化影响 Agent-facing 工具视图时，Computer SHOULD 发送 `server:update_tool_list`。

## 6. Source Convergence

Tool exposure policy MAY come from user config、plugin、organization policy 或其它 trusted management source。Computer MUST reconcile these policies into a single Agent-facing tool view.

Conflicting tool aliases or exposure policies MUST NOT be resolved randomly. Computer MUST follow a documented source precedence policy, mark the tool `conflicted`, require trusted-local resolution, or reject the management operation. User-authored local policy SHOULD override plugin-provided policy unless deployment policy says otherwise.

Source precedence is SDK/deployment policy, not a wire contract. Agent-facing conformance only requires that the final `SMCPTool.name` set be unique, deterministic and safe to route.
