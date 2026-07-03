# Computer Management Plane

本文定义 Computer Management Plane 的协议定位与模块目录。它面向可信本地客户端，例如桌面 App、管理 UI、CLI 或嵌入式 SDK 调用方，用于管理 Computer 的 desired state。

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

管理面可以是进程内 SDK API、本地 RPC、CLI 或平台私有 API。A2C-SMCP 不规定其传输、函数名、权限模型或 UI 形态；本目录只规定它与 Agent-facing 协议面的边界，以及管理操作完成后必须满足的可观察结果。

## 2. 规范性边界

本目录同时包含协议义务和 SDK guidance。判定规则如下：

| 层级 | 本目录可以规定 | 本目录不得规定 |
|---|---|---|
| Protocol requirement | Agent / Server 可通过 `client:*`、`server:update_*`、`notify:*` 或错误 payload 观察到的行为；安全与授权边界；禁用、移除、冲突后的 Agent-facing 投影 | 本地 API 名称、CLI 命令、文件布局、锁、缓存、watcher、进程模型、下载器、安装器、迁移算法 |
| SDK guidance | 推荐管理对象、状态名、reconcile pipeline、诊断类别、source precedence 文档化方式 | 作为跨语言 conformance 的唯一判据 |
| Reference detail | 某个 SDK 的目录、函数、trait、测试 fixture、临时 workaround | 提升为任何合规 Computer 都必须实现的规则 |

除非某段文字明确约束 Agent-facing projection、Socket.IO 事件、错误形状、房间隔离或 secret 暴露，否则其中的管理操作、状态名和 pipeline 只是 SDK guidance。合规性通过以下可观察结果判断：

1. 管理操作完成或被接受后，Agent 通过既有 `client:get_config`、`client:get_tools`、`client:get_desktop`、`client:get_resources`、`client:get_skills`、`client:get_skill` 和 `client:get_blob` 看到的状态必须满足对应协议章节。
2. 管理操作导致 Agent-facing projection 变化且 Computer 已 `online` 时，Computer 应按 [Reconcile and Notifications](reconcile-and-notifications.md) 发送相应 `server:update_*` 刷新提示。
3. 失败、禁用、forbidden、hidden、orphaned、removed、invalid 或 policy-rejected 的能力不得作为可用能力暴露给 Agent。
4. 管理面诊断、路径、安装日志、secret、env 文件内容、OAuth token、stack trace 或本地 cache metadata 不得进入任何 Agent-facing 响应、工具元数据、Desktop 内容、SKILL/Blob 响应或 update notification。

本目录不定义新的 Agent-facing Socket.IO 事件，也不定义远程管理 RPC。若实现提供远程管理面，认证、授权、审计和传输格式属于部署/SDK 责任；协议只要求该管理面不能绕过本目录列出的 Agent-facing 安全与投影边界。

## 3. 设计原则

1. **Trusted local only**：管理面默认由 Computer 所在宿主环境或同等可信控制面调用，不暴露给普通 Agent。
2. **Desired state first**：管理操作表达期望状态，例如 server enabled、plugin installed、skill exposed；Computer 负责 reconcile 到运行状态。
3. **Protocol result visibility**：管理操作完成后，Agent 通过 `client:get_config`、`client:get_tools`、`client:get_skills`、`client:get_desktop` 等观察结果。
4. **No secret propagation**：输入值、API key、OAuth token、`.skillenv` 与本地凭据只在 Computer 本地解析，不进入 Agent-facing 响应。
5. **Idempotent where practical**：重复执行 install/enable/disable/sync/remove 等操作 SHOULD 得到稳定结果，或返回明确的管理面错误。

## 4. 模块目录

| 模块 | 管理什么 | 不管理什么 |
|---|---|---|
| [Lifecycle](lifecycle.md) | 管理面与 Computer runtime 的整体状态、启动、关闭、reload、并发边界 | 具体 MCP Server、SKILL、plugin 的业务状态 |
| [Connection](connection.md) | Computer runtime 与 SMCP Server / robot / Office 的连接、断开、重连、join/leave office | 从 `ComputerHome` 启动 runtime |
| [Capability Sources](capability-sources.md) | marketplace / plugin / user / MCP resource 贡献能力的 provenance、冲突、收敛、撤销 | 下载、安装、缓存和本地目录布局 |
| [MCP Server](mcp-server.md) | MCP Server 配置、desired state、runtime state、启停、健康与 Agent-facing 投影 | 工具级 alias/forbidden 细节 |
| [Tool Exposure](tool-exposure.md) | 工具可见性、可调用性、别名、disabled/forbidden、元数据和重名冲突 | MCP Server 进程生命周期 |
| [SKILL Exposure](skill-exposure.md) | user / mcp / marketplace / plugin source SKILL 的安装、物化、显隐、孤儿与 sandbox 投影 | marketplace source 本身的同步策略 |
| [Marketplace](marketplace.md) | marketplace source 的配置、同步、搜索、认证和索引诊断 | 已安装 plugin 的 enable/disable 语义 |
| [Plugin](plugin.md) | plugin 安装、更新、启停、卸载及其提供的 managed capability | marketplace 索引发现策略 |
| [Inputs and Secrets](inputs-and-secrets.md) | input 定义、值缓存、secret store、OAuth 状态与本地解析边界 | Agent-facing secret 传输 |
| [Reconcile and Notifications](reconcile-and-notifications.md) | desired state 变更后的 validate/apply/discover/publish 流程与 `server:update_*` 通知 | 单个对象的完整状态机 |
| [Management Errors](errors.md) | 管理面错误类别、诊断结构、partial failure 与 Agent-facing 错误边界 | `client:*` 协议错误码全集 |
| [Management Security](security.md) | 管理面的高权限边界、诊断隔离、source 信任策略与禁用后的强制不可见 | Socket.IO 房间隔离细节 |

## 5. 管理对象

Computer Management Plane 至少覆盖下列对象类别：

| 对象 | 说明 | Agent-facing 投影 |
|---|---|---|
| Capability source | marketplace / plugin / user / MCP resource 等能力来源 | 通常不直接暴露；安全 provenance 可进入既有字段 |
| MCP Server | Computer 纳管的 MCP Server 配置与运行状态 | `client:get_config`、`client:get_tools`、`client:get_resources`、Desktop、MCP source SKILL |
| Tool exposure | 工具启用、禁用、别名、forbidden 规则、元数据 | `client:get_tools`、`client:tool_call` |
| SKILL exposure | user / marketplace / MCP source SKILL 的安装、物化、显隐、刷新 | `client:get_skills`、`client:get_skill`、`client:get_blob` |
| Marketplace | 可安装 plugin / SKILL 的来源仓库或索引 | 通常不直接暴露；安装结果投影为 SKILL / MCP / plugin 能力 |
| Plugin | 可带 MCP Server、SKILL、配置模板或本地扩展的包 | 安装结果投影为 MCP Server、工具、SKILL 或配置 |
| Inputs / secrets | 本地输入定义、值缓存、secret 解析策略 | `client:get_config` 只暴露安全定义，不暴露 secret 值 |

## 6. 兼容性

本目录为 **protocol boundary clarification + SDK guidance**。兼容性标签为 Documentation-only / Tightening：

- 不新增 Agent-facing Socket.IO 事件。
- 不改变现有 `client:*` 请求/响应 shape。
- 不要求 Server 理解 marketplace、plugin 或本地管理操作。
- Tightening 部分只澄清：管理结果不得破坏既有 Agent-facing 协议、安全边界和错误形状。
- SDK guidance 部分推荐提供一致的管理面能力，但不作为 wire conformance 的单独要求。
