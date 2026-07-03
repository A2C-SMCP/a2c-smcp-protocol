# Computer Management Plane

本文定义 Computer 侧管理面的协议边界、SDK API 语义和 conformance tests。它面向可信本地客户端，例如桌面 App、管理 UI、CLI、SDK 嵌入方或本地管理代理，用于把声明式 desired state 收敛为一个运行中的 Computer。

Computer Management Plane 不是 Agent-facing SMCP `client:*` 事件面。Agent 不能通过本管理面直接启动/停止 MCP Server、安装 plugin、同步 marketplace、读取本地文件或修改 secret。合规性通过管理操作完成后 Agent 可观察到的 `client:get_*` 响应、`server:update_*` 通知、安全边界和公共 SDK 结果来验证。

## 1. 分层模型

```
Trusted local client / admin UI / CLI
        |
        v
Computer Management Plane
        | mutate desired state
        v
Computer runtime
        | expose observable state
        v
SMCP Protocol Plane
        |
        v
Agent
```

| Layer | Consumer | Producer | 作用 |
|---|---|---|---|
| Computer Management Plane | 可信本地客户端 | Computer SDK / admin adapter | 修改 Computer desired state、管理本地能力 |
| Computer Runtime Contract | 业务 client / SDK 作者 | Computer SDK | 定义跨语言一致的单 Computer runtime 语义 |
| SMCP Protocol Plane | Agent / Server | Computer | 暴露工具、配置、Desktop、SKILL、Blob 与更新通知 |

管理面可以是进程内 SDK API、本地 RPC、CLI 或平台私有 API。A2C-SMCP 不规定它的传输、函数名、权限模型或 UI 形态；本目录只规定它与 Agent-facing 协议面的边界，以及 SDK 公共能力必须具备的跨语言语义。

## 2. 文档目录

| 文档 | 内容 | 规范性 |
|---|---|---|
| [Management Protocol Boundary](protocol.md) | 管理面与 Agent-facing 协议面的边界、投影规则、安全边界与证据摘要 | Protocol requirements + boundary clarification |
| [Computer Runtime Contract](runtime-contract.md) | 从声明式 config 创建、启动、连接、同步、停止、关闭一个 runtime Computer 的跨 SDK 语义 | Runtime-contract |
| [SDK API Guidance](sdk-api-guidance.md) | SDK 应提供的稳定能力族、错误分类、实现建议和迁移建议 | Non-normative SDK guidance |
| [Conformance Tests](conformance-tests.md) | 协议级与 runtime contract 级共享测试清单、fixture 形状和验收矩阵 | SDK conformance checklist |

## 3. 规范性边界

本目录同时包含协议义务、runtime contract 和 SDK guidance。判定规则如下：

| 层级 | 可以规定 | 不得规定 |
|---|---|---|
| Protocol requirement | Agent / Server 可通过 `client:*`、`server:update_*`、`notify:*` 或错误 payload 观察到的行为；安全与授权边界；禁用、移除、冲突后的 Agent-facing 投影 | 本地 API 名称、CLI 命令、文件布局、锁、缓存、watcher、进程模型、下载器、安装器、迁移算法 |
| Runtime contract | 业务 client 可跨 SDK 依赖的单 Computer runtime 公共语义、状态迁移、错误分类、config fixture 解析结果 | Python dataclass、Rust builder、TypeScript class、trait 名、async runtime 或内部 registry |
| SDK guidance | 推荐能力族、测试入口、实现策略、迁移与诊断建议 | 作为 wire protocol 的唯一判据 |
| Reference detail | 某个 SDK 的目录、函数、trait、测试 fixture、临时 workaround | 提升为任何合规 Computer 都必须实现的规则 |

除非某段文字明确约束 Agent-facing projection、Socket.IO 事件、错误 shape、房间隔离、secret 暴露或公共 SDK 语义，否则其中的管理操作、状态名和 pipeline 都是 SDK guidance。

## 4. 合规性原则

1. 管理操作完成或被接受后，Agent 通过既有 `client:get_config`、`client:get_tools`、`client:get_desktop`、`client:get_resources`、`client:get_skills`、`client:get_skill` 和 `client:get_blob` 看到的状态 MUST 满足对应协议章节。
2. 管理操作导致 Agent-facing projection 变化且 Computer 已加入 Office 时，Computer SHOULD 发送相应 `server:update_*` 刷新提示。
3. 失败、禁用、forbidden、hidden、orphaned、removed、invalid 或 policy-rejected 的能力 MUST NOT 作为可用能力暴露给 Agent。
4. 管理面诊断、路径、安装日志、secret、env 文件内容、OAuth token、stack trace 或本地 cache metadata MUST NOT 进入任何 Agent-facing 响应、工具元数据、Desktop 内容、SKILL/Blob 响应或 update notification。
5. Runtime contract conformance MUST 能通过公共 SDK 结果、公开事件、wire 行为、错误分类或安全边界验证；不得要求读取私有缓存、锁、任务图或目录布局。

## 5. 兼容性

本目录为 **protocol boundary clarification + Runtime-contract + SDK guidance**：

- 不新增 Agent-facing Socket.IO 事件。
- 不改变现有 `client:*` 请求/响应 shape。
- 不要求 Server 理解 marketplace、plugin 或本地管理操作。
- Tightening 部分只澄清：管理结果不得破坏既有 Agent-facing 协议、安全边界和错误 shape。
- Runtime-contract 部分需要 SDK 通过共享 fixture 和生命周期 conformance tests 对齐公共语义。
