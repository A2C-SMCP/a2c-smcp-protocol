# Plugin Management

本文定义管理面如何安装、更新、启用、禁用和卸载 plugin。Plugin 可以提供 MCP Server 配置、SKILL 包、工具元数据策略、input 定义或复合能力。

## 1. 管理范围

本模块管理：

- plugin identity：plugin id、version、marketplace provenance。
- plugin 状态：available / installed / enabled / disabled / updating / invalid / removed。
- list / install / update / enable / disable / remove / diagnostics。
- plugin manifest 的管理面语义边界。
- plugin 提供的 managed capability 如何 reconcile 到其它模块。
- plugin 作为 `plugin:<plugin_id>` capability source 的 provenance 与撤销边界。

本模块不管理：

- marketplace 索引发现，见 [Marketplace](marketplace.md)。
- 多来源能力冲突与 provenance 通用规则，见 [Capability Sources](capability-sources.md)。
- MCP Server runtime 启停细节，见 [MCP Server](mcp-server.md)。
- SKILL sandbox 读取细节，见 [SKILL Exposure](skill-exposure.md)。

## 2. 状态

| State | 含义 | Agent-facing 投影 |
|---|---|---|
| `available` | 可安装但未安装 | 无直接投影 |
| `installed` | 已安装但是否启用取决于 enabled | 取决于 enabled |
| `enabled` | plugin 提供的能力允许 reconcile | 相关 MCP/SKILL/tool/config 可见 |
| `disabled` | plugin 保留但能力不可见/不可调用 | 相关能力 MUST 不可见或不可调用 |
| `updating` | 正在更新版本 | MAY 保持旧投影直到 reconcile 完成 |
| `invalid` | manifest、兼容性或策略失败 | 不应暴露其能力 |
| `removed` | 已卸载 | 后续 Agent-facing 响应不再包含相关能力 |

## 3. Operations

| 能力 | 语义 | 完成后的协议投影 |
|---|---|---|
| list plugins | 列出已安装 plugin 与状态 | 不要求通知 |
| install plugin | 安装 plugin 包并 reconcile 其能力 | 可能触发 config/tool/skills/desktop 更新 |
| update plugin | 更新 plugin 版本并 reconcile | 按实际变化发送 update |
| enable plugin | 启用 plugin 提供的 MCP/SKILL/配置 | 相关能力可见 |
| disable plugin | 禁用 plugin 提供的能力 | 相关能力不可见或不可调用 |
| remove plugin | 卸载 plugin 并清理其 managed capability | 后续 Agent-facing 响应不再包含相关能力 |
| get plugin diagnostics | 查看安装、兼容性、权限与冲突诊断 | 不进入 Agent-facing 协议 |

## 4. Managed Capability

Plugin MAY 提供：

- MCP Server config。
- SKILL packages。
- tool metadata policy。
- input definitions。
- marketplace 或其它 source 配置。

Plugin 提供的内容是 managed capability，不是 Agent-facing projection 本身。Computer MUST 把 plugin-contributed capability 交给对应模块 reconcile：MCP Server config 进入 [MCP Server](mcp-server.md)，SKILL packages 进入 [SKILL Exposure](skill-exposure.md)，tool metadata policy 进入 [Tool Exposure](tool-exposure.md)，input definitions 进入 [Inputs and Secrets](inputs-and-secrets.md)。

安装后的 Agent-facing 投影 MUST 满足现有 `client:get_*` 与安全规则。plugin 与手工配置冲突时，管理面 SHOULD 返回 conflict 诊断，或按 [Capability Sources](capability-sources.md) 中的文档化 source precedence policy 决定优先级。

禁用或移除 plugin 后，Computer MUST reconcile all capabilities contributed by `plugin:<plugin_id>`，并使其不再作为可用 Agent-facing 能力投影。
