# Computer Management Plane

本文定义 Computer Management Plane 的协议定位与 SDK/admin surface 期望。它面向可信本地客户端，例如桌面 App、管理 UI、CLI 或嵌入式 SDK 调用方，用于管理 Computer 的 desired state。

Computer Management Plane **不是** Agent-facing SMCP `client:*` 事件面。Agent 不能通过本管理面直接启动/停止 MCP Server、安装 plugin、同步 marketplace 或修改本地 secret。协议一致性通过这些管理操作完成后的 Agent 可见状态与 `server:update_*` 通知来衡量。

## 1. 分层模型

```
Trusted local client / admin UI / CLI
        │
        ▼
Computer Management Plane
        │  mutate desired state
        ▼
Computer runtime
        │  expose observable state
        ▼
SMCP Protocol Plane
        │
        ▼
Agent
```

| Plane | Consumer | Producer | 作用 |
|---|---|---|---|
| Computer Management Plane | 可信本地客户端 | Computer SDK / admin adapter | 修改 Computer desired state、管理本地能力 |
| SMCP Protocol Plane | Agent / Server | Computer | 暴露工具、配置、Desktop、SKILL、Blob 与更新通知 |

管理面可以是进程内 SDK API、本地 RPC、CLI 或平台私有 API。A2C-SMCP 不规定其传输、函数名、权限模型或 UI 形态；本页只规定它与 Agent-facing 协议面的边界，以及管理操作完成后必须满足的可观察结果。

## 2. 设计原则

1. **Trusted local only**：管理面默认由 Computer 所在宿主环境或同等可信控制面调用，不暴露给普通 Agent。
2. **Desired state first**：管理操作表达期望状态，例如 server enabled、plugin installed、skill exposed；Computer 负责 reconcile 到运行状态。
3. **Protocol result visibility**：管理操作完成后，Agent 通过 `client:get_config`、`client:get_tools`、`client:get_skills`、`client:get_desktop` 等观察结果。
4. **No secret propagation**：输入值、API key、OAuth token、`.skillenv` 与本地凭据只在 Computer 本地解析，不进入 Agent-facing 响应。
5. **Idempotent where practical**：重复执行 install/enable/disable/sync/remove 等操作 SHOULD 得到稳定结果，或返回明确的管理面错误。

## 3. 管理对象

Computer Management Plane 至少覆盖下列对象类别：

| 对象 | 说明 | Agent-facing 投影 |
|---|---|---|
| MCP Server | Computer 纳管的 MCP Server 配置与运行状态 | `client:get_config`、`client:get_tools`、`client:get_resources`、Desktop、MCP source SKILL |
| Tool exposure | 工具启用、禁用、别名、forbidden 规则、元数据 | `client:get_tools`、`client:tool_call` |
| SKILL exposure | user / marketplace / MCP source SKILL 的安装、物化、显隐、刷新 | `client:get_skills`、`client:get_skill`、`client:get_blob` |
| Marketplace | 可安装 plugin / SKILL 的来源仓库或索引 | 通常不直接暴露；安装结果投影为 SKILL / MCP / plugin 能力 |
| Plugin | 可带 MCP Server、SKILL、配置模板或本地扩展的包 | 安装结果投影为 MCP Server、工具、SKILL 或配置 |
| Inputs / secrets | 本地输入定义、值缓存、secret 解析策略 | `client:get_config` 只暴露安全定义，不暴露 secret 值 |

## 4. 推荐管理能力

本节是 SDK/admin surface guidance，不是 Agent-facing wire API。不同语言 SDK 可以使用不同函数名，只要语义覆盖即可。

### 4.1 MCP Server 管理

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

### 4.2 Tool exposure 管理

| 能力 | 语义 | 完成后的协议投影 |
|---|---|---|
| list tools | 查看当前管理面工具视图，含禁用/冲突原因 | 不要求通知 |
| enable tool | 允许工具出现在 Agent 可见工具列表 | `client:get_tools` 可见 |
| disable tool | 从 Agent 可见工具列表移除工具 | `client:get_tools` 不再返回 |
| forbid tool | 强制禁止工具被 Agent 调用 | 不出现在 `client:get_tools`，且 `client:tool_call` 不得成功执行 |
| set alias | 为工具设置 Agent 可见唯一名称 | `SMCPTool.name` 或 `meta.a2c_tool_meta.alias` 按规范呈现 |
| set metadata | 设置 tags、auto_apply 等 A2C 元数据 | `SMCPTool.meta["a2c_tool_meta"]` 更新 |

如果管理面允许同名工具共存，Computer MUST 在 Agent-facing 工具面保证最终可调用名称唯一可路由，见 [Computer 侧协议框架 §工具列表](computer.md#42-工具列表)。

### 4.3 SKILL 管理

| 能力 | 语义 | 完成后的协议投影 |
|---|---|---|
| list skills | 列出所有管理面 SKILL，含 hidden/orphan/error 状态 | 不要求通知 |
| refresh skills | 重新扫描 source 并 reconcile Registry | 变化时 `server:update_skills` |
| install user skill | 从本地包或目录安装 user source SKILL | 活跃时进入 `client:get_skills` |
| expose skill | 允许 SKILL 对 Agent 可见 | `client:get_skills` 返回该 SKILL |
| hide skill | 让 SKILL 对 Agent 不可见但可保留本地安装 | `client:get_skills` 不返回该 SKILL |
| remove skill | 删除或注销 SKILL | 后续 `client:get_skill` 返回 `4014` |
| read skill diagnostics | 返回 staging / frontmatter / sandbox 诊断 | 不进入 Agent-facing 协议 |

隐藏、安装失败、frontmatter 错误、source orphan 等管理面状态 MAY 对管理员可见，但 MUST NOT 通过 `client:get_skills` 暴露为可用 SKILL。

### 4.4 Marketplace 管理

| 能力 | 语义 | 完成后的协议投影 |
|---|---|---|
| list marketplaces | 列出已配置 marketplace source | 不要求通知 |
| add marketplace | 新增 marketplace source | 通常不直接通知；安装/同步结果触发 |
| remove marketplace | 移除 marketplace source，并按策略处理已安装 plugin/SKILL | 受影响能力变化时发送 update |
| sync marketplace | 拉取或刷新 marketplace 索引 | 若安装集合不变，不要求通知 |
| search marketplace | 查询可安装 plugin/SKILL | 不进入 Agent-facing 协议 |

Marketplace metadata、认证、索引缓存、版本解析、签名校验与网络重试属于管理面实现策略。若这些操作改变已安装 plugin 或 SKILL，Computer SHOULD 通过对应 `server:update_*` 通知 Agent 重新拉取。

### 4.5 Plugin 管理

| 能力 | 语义 | 完成后的协议投影 |
|---|---|---|
| list plugins | 列出已安装 plugin 与状态 | 不要求通知 |
| install plugin | 安装 plugin 包并 reconcile 其能力 | 可能触发 config/tool/skills/desktop 更新 |
| update plugin | 更新 plugin 版本并 reconcile | 按实际变化发送 update |
| enable plugin | 启用 plugin 提供的 MCP/SKILL/配置 | 相关能力可见 |
| disable plugin | 禁用 plugin 提供的能力 | 相关能力不可见或不可调用 |
| remove plugin | 卸载 plugin 并清理其 managed capability | 后续 Agent-facing 响应不再包含相关能力 |
| get plugin diagnostics | 查看安装、兼容性、权限与冲突诊断 | 不进入 Agent-facing 协议 |

Plugin 可以是纯 SKILL 包、MCP Server 配置包、工具元数据包或复合包。协议不规定 plugin manifest 格式；但安装后的 Agent-facing 投影 MUST 满足现有 `client:get_*` 与安全规则。

### 4.6 Inputs 与 secrets 管理

管理面 MAY 提供 input 定义、默认值、用户填写值、secret store、OAuth 授权状态等管理能力。完成后的 Agent-facing 投影有两个限制：

1. `client:get_config` MAY 暴露 input 定义和非敏感配置，但 MUST NOT 暴露 resolved secret value。
2. 工具启动和 MCP Server 连接所需 secret MUST 在 Computer 本地解析；Agent 参数中的 token / secret 字段 MUST NOT 被视为可信凭据。

## 5. Reconcile 与通知

管理操作 SHOULD 经过 reconcile 阶段，把 desired state 转成 Computer runtime state。reconcile 完成后，如果 Agent 可见状态变化，Computer SHOULD 发送对应 update 事件：

| 变化类型 | 推荐通知 |
|---|---|
| MCP Server 配置、input 定义或 Agent 可见配置变化 | `server:update_config` |
| 工具集合、工具别名、禁用/forbidden 规则或工具元数据变化 | `server:update_tool_list` |
| `window://` 集合或内容变化 | `server:update_desktop` |
| SKILL 集合、frontmatter、可见性或包内容变化 | `server:update_skills` |

通知可以合并，但合并后 SHOULD 保证 Agent 通过对应 `client:get_*` 能拉到最新状态。管理面操作的成功返回不等价于 Agent 已消费更新；它只表示 Computer 已完成或接受了 desired state 变更。

## 6. 管理面错误

Computer Management Plane 的错误可以比 Agent-facing 错误更丰富，例如：

| 错误类别 | 示例 |
|---|---|
| validation | 配置 schema 错误、plugin manifest 错误、SKILL frontmatter 错误 |
| conflict | 同名 MCP Server、工具 alias 冲突、SKILL name 冲突 |
| lifecycle | 启动失败、停止超时、健康检查失败、重连耗尽 |
| authorization | marketplace 凭据失效、plugin source 无权限、OAuth 未完成 |
| policy | 工具被 forbidden、plugin 被组织策略禁止、source 不可信 |

这些错误不必映射为 Agent-facing `ErrorPayload`。只有当 Agent 调用 `client:*` 时，才使用 [错误处理](error-handling.md) 定义的协议级错误或 MCP `CallToolResult.isError`。

## 7. 安全要求

1. 管理面 MUST 被视为高权限 surface，部署方 MUST 保护其访问边界。
2. 管理面 MAY 返回本地诊断、路径、日志或安装错误；这些信息 MUST NOT 自动进入 Agent-facing SMCP 响应。
3. 管理面不得把 secret 注入 Agent-facing `client:get_config`、`client:get_skills`、`client:get_skill`、`client:get_blob` 或 tool metadata。
4. 从 marketplace / plugin 安装的内容在暴露为 SKILL 或 MCP capability 前 SHOULD 经过本地策略校验。
5. 管理面禁用或移除能力后，Computer MUST 尽快使 Agent-facing 能力不可见或不可调用。

## 8. 兼容性

本页为 **SDK guidance + protocol boundary clarification**：

- 不新增 Agent-facing Socket.IO 事件。
- 不改变现有 `client:*` 请求/响应 shape。
- 不要求 Server 理解 marketplace、plugin 或本地管理操作。
- 对 SDK 的影响是推荐提供一致的管理面能力，并把管理结果正确投影到现有协议面。

