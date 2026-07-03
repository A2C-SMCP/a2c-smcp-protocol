# MCP Server Management

本文定义 Computer Management Plane 中 MCP Server 的管理语义。它管理 MCP Server 配置、desired state、runtime state、启停、健康诊断，以及这些变化如何投影到 Agent-facing SMCP 协议面。

## 1. 管理范围

本模块管理：

- MCP Server identity 与配置存在性。
- server desired state：present / enabled / disabled / removed。
- runtime state：stopped / starting / running / unhealthy / stopping / failed。
- add / update / remove / enable / disable / start / stop / restart / status。
- MCP Server 配置变化对 tools、resources、Desktop、MCP source SKILL 的影响。
- health / reconnect / last error 的管理面诊断边界。
- MCP Server 作为 `mcp:<server_name>` SKILL source 的生命周期边界。

本模块不管理：

- 工具级 alias、disabled、forbidden 和元数据，见 [Tool Exposure](tool-exposure.md)。
- SKILL 的 staging、sandbox 和可见性，见 [SKILL Exposure](skill-exposure.md)。
- 多来源能力贡献和冲突规则，见 [Capability Sources](capability-sources.md)。
- 管理面传输、CLI 命令或 SDK 函数名。

## 2. Identity

每个 MCP Server 在单个 Computer Management Plane 内 MUST 有唯一 `server_name`。该名字是 `client:get_config` 中 `servers` 字典 key，也是 `client:get_resources.mcp_server` 的路由键。

管理面若支持 rename，MUST 把 rename 视为影响 Agent-facing 投影的配置变化：旧 `server_name` 后续 MUST NOT 成功路由，新 `server_name` 应通过 `client:get_config` 可见。

## 3. Desired State

| State | 含义 | Agent-facing 投影 |
|---|---|---|
| `present` | 配置存在，但是否启用由 enabled 标志决定 | 取决于 enabled/runtime |
| `enabled` | 允许启动并暴露能力 | runtime 可用后投影工具/资源/SKILL/Desktop |
| `disabled` | 配置保留但禁止暴露能力 | 相关能力 MUST 不可见或不可调用 |
| `removed` | 配置已删除 | 后续投影 MUST 移除相关能力 |

禁用或移除 MCP Server 后，Computer MUST NOT 成功执行该 Server 的工具。

## 4. Runtime State

| State | 含义 | Agent-facing 投影 |
|---|---|---|
| `stopped` | runtime 未运行或未连接 | SHOULD 不暴露其运行时能力 |
| `starting` | 正在启动或连接 | MAY 暂不暴露新能力 |
| `running` | 已连接并完成能力发现 | SHOULD 暴露 enabled 能力 |
| `unhealthy` | 已存在但能力可能不可用 | SHOULD 通过管理面诊断；Agent-facing 能力可按实现降级 |
| `stopping` | 正在停止 | SHOULD 尽快移除可调用能力 |
| `failed` | 启动或运行失败 | MUST NOT 暴露不可调用工具为可成功调用 |

health、last error、重连次数、退避状态属于管理面诊断，不直接进入 Agent-facing 协议。

## 5. Operations

| 能力 | 语义 | 完成后的协议投影 |
|---|---|---|
| list servers | 列出已知 MCP Server desired/runtime 状态 | 不要求通知 |
| add server | 新增 MCP Server 配置，可选择立即启动 | `server:update_config`；若工具变化则 `server:update_tool_list` |
| update server | 修改 MCP Server 配置并 reconcile | `server:update_config`，并按影响发送 tool/desktop/skills 更新 |
| enable server | 允许该 Server 暴露能力并可启动 | 相关工具 / 资源 / SKILL 可被发现 |
| disable server | 禁止该 Server 暴露能力并停止可调用性 | 相关工具从 `client:get_tools` 消失，工具调用不得成功 |
| start server | 启动或连接 MCP Server runtime | 成功后能力进入可发现状态 |
| stop server | 停止或断开 MCP Server runtime | 相关能力进入不可见或不可用状态 |
| restart server | 停止后重新启动并刷新能力 | 按变化发送 update 通知 |
| remove server | 删除配置并停止 runtime | 相关工具、Desktop、MCP source SKILL 不再可见 |
| get server status | 查看 runtime health / last error | 不要求进入 Agent-facing 协议 |

## 6. Agent-Facing Effects

MCP Server lifecycle 变化可能影响：

- `client:get_config`
- `client:get_tools`
- `client:get_resources`
- `client:get_desktop`
- `client:get_skills`
- `client:get_skill`
- `client:get_blob`

配置变化 SHOULD 触发 `server:update_config`。工具集合变化 SHOULD 触发 `server:update_tool_list`。`window://` 变化 SHOULD 触发 `server:update_desktop`。MCP source SKILL 变化 SHOULD 触发 `server:update_skills`。

## 7. MCP Source SKILL

当 enabled 且 running 的 MCP Server 通过 `resources/list` 暴露 `skill://` resources 时，Computer SHOULD 将其作为 `mcp:<server_name>` source 贡献给 [SKILL Exposure](skill-exposure.md)。

MCP Server stopped / disabled / removed 后，其贡献的 MCP source SKILL MUST 不再作为可用 SKILL 出现在 `client:get_skills`。临时断连、重连恢复、资源消失和 orphan 策略见 [Capability Sources §MCP Resource SKILL](capability-sources.md#7-mcp-resource-skill)。
