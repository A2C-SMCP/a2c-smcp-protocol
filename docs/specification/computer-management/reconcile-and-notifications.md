# Reconcile and Notifications

本文定义 Computer Management Plane 中 desired state 变更后的结果契约，以及 Agent-facing `server:update_*` 通知边界。

Reconcile 的协议重点是外部可观察结果：Computer 在管理面配置变化后，必须把 Agent-facing projection 收敛到安全、一致、基于实际成功 runtime state 的状态。具体 diff、plan、锁、缓存和执行算法属于 SDK guidance。

## 1. 管理范围

本模块管理：

- desired state 变更后的外部结果契约。
- runtime state 与 Agent-facing projection 的关系。
- failed / disabled / forbidden / hidden / removed capability 的不可见或不可调用规则。
- 哪些 projection 变化触发哪些 `server:update_*`。
- 通知 coalescing 与 Agent 主动拉取之间的关系。
- partial failure 的可见性与 diagnostics 边界。

本模块不管理：

- 单个对象的完整状态机。
- 具体 diff / plan 算法。
- 本地 class、trait、锁、缓存、任务队列或落盘格式。
- Server 如何广播 `notify:*`，见 [事件定义](../events.md)。

## 2. Normative Requirements

### 2.1 Projection 基于实际成功状态

Computer MUST publish Agent-facing projection from successfully applied runtime state, not from unapplied desired state.

这意味着：

1. 如果 MCP Server 配置存在但启动失败，其工具 MUST NOT 作为可成功调用能力暴露。
2. 如果 plugin 安装失败，其提供的 MCP Server、SKILL、tool metadata 或 input definition MUST NOT 作为成功能力投影。
3. 如果 SKILL staging 或 sandbox 校验失败，该 SKILL MUST NOT 出现在 `client:get_skills`。
4. 如果 marketplace sync 成功但没有改变 installed/exposed 能力，不要求 Agent-facing projection 变化。

### 2.2 不可用能力不得暴露为可用

Computer MUST NOT expose failed, disabled, forbidden, hidden, removed, invalid, or policy-rejected capabilities as available Agent-facing capabilities.

具体要求：

| 管理面状态 | Agent-facing 要求 |
|---|---|
| disabled MCP Server | 相关工具 / Desktop / MCP source SKILL MUST 不可见或不可调用 |
| forbidden tool | MUST 不出现在 `client:get_tools`，且 `client:tool_call` MUST NOT 成功执行 |
| hidden SKILL | MUST 不出现在 `client:get_skills` |
| orphaned SKILL | MUST 不出现在 `client:get_skills` |
| removed plugin | 其 managed capability MUST 从后续 projection 中移除 |
| invalid marketplace/plugin/SKILL | MUST 不作为成功能力投影 |

If an Agent tries to use a capability after it has become unavailable, Computer MUST use the existing protocol shape for that channel:

| Channel | Unavailable result |
|---|---|
| `client:get_tools` | Omit disabled / forbidden / conflicted / unavailable tools |
| `client:tool_call` | If routed to Computer, return MCP `CallToolResult(isError=true)` and do not execute the underlying tool |
| `client:get_desktop` | Omit unavailable windows; exact `window` lookup for a removed window returns empty `desktops` as defined by Desktop |
| `client:get_resources` | Unknown or removed `mcp_server` returns existing `4014`; missing resources capability returns `4015` |
| `client:get_skills` | Omit hidden / orphaned / invalid / removed SKILLs |
| `client:get_skill` | Legal but unavailable name returns existing not-found semantics (`4014`); illegal name remains `4016`; sandbox/resource failures remain `4017` |
| `client:get_blob` | Previously minted handle whose source is now unauthorized or gone returns `4018` with the existing reason model |

Management errors MUST NOT introduce a new Agent-facing error envelope. Except for `client:tool_call`, protocol-level `client:*` failures remain flat `ErrorPayload`; tool execution failures remain MCP `CallToolResult`.

### 2.3 Projection 变化应通知

When Agent-facing projection changes while Connection state is `online`, Computer SHOULD send the corresponding `server:update_*` event. If an implementation cannot determine a minimal diff, it MAY send the broader relevant update event; the event is a refresh hint, not the state payload.

| Projection 变化类型 | 推荐通知 |
|---|---|
| MCP Server 配置、input 定义或 Agent 可见配置变化 | `server:update_config` |
| 工具集合、工具别名、禁用/forbidden 规则或工具元数据变化 | `server:update_tool_list` |
| `window://` 集合或内容变化 | `server:update_desktop` |
| SKILL 集合、frontmatter、可见性或包内容变化 | `server:update_skills` |

通知可以合并，但合并后 SHOULD 保证 Agent 通过对应 `client:get_*` 能拉到最新 projection. Debounce interval, dirty-flag representation and batching algorithm are SDK guidance.

### 2.4 Offline 不发送通知

When Connection state is not `online`, Computer MUST NOT send `server:update_*` events because there is no valid Office route.

Computer MAY continue to update desired state, runtime state, diagnostics and local projection while offline. After reconnect and entering `online`, Agent MUST be able to read the current successfully reconciled projection through the corresponding `client:get_*` events. Computer MAY send one or more `server:update_*` events after reconnect as refresh hints, but Agent correctness MUST NOT depend on receiving a complete diff through notifications.

### 2.5 Diagnostics 留在管理面

Computer MUST keep reconcile diagnostics in the management plane. It MUST NOT leak local secrets, absolute paths, install logs, stack traces, source credentials, or internal cache details into Agent-facing responses, tool metadata, Desktop content, SKILL responses, Blob responses, or update notifications.

## 3. 成功语义

管理操作的成功返回不等价于 Agent 已刷新。它只表示 Computer 已完成或接受 desired state 变更。Agent 仍需通过 `notify:*` 或主动拉取 `client:get_*` 观察新 projection。

管理操作 MAY 返回以下类型的结果：

| 结果 | 含义 |
|---|---|
| accepted | desired state 已被接受，但 reconcile 可能异步进行 |
| applied | desired state 已应用到 runtime |
| published | Agent-facing projection 已更新；若 online，通知已发送或已排队 |
| partial | 部分对象成功，部分对象失败，详见 diagnostics |
| failed | 未产生新的成功 projection |

这些结果属于管理面，不直接映射为 Agent-facing `ErrorPayload`。

## 4. Partial Failure

当 reconcile 部分成功、部分失败时，Computer SHOULD：

- 只发布已经安全且一致的 Agent-facing projection。
- 把失败详情保留在管理面 diagnostics。
- 不通过 Agent-facing 响应暴露本地 secret、路径或内部日志。
- 对不可安全投影的对象保持 hidden / unavailable / invalid。
- 在 diagnostics 中说明哪些对象成功、哪些对象失败，以及失败是否可重试。

Partial failure MUST NOT cause failed capability to appear as available.

## 5. Recommended Pipeline (Non-normative)

以下流水线是 SDK guidance，用于处理复杂配置。实现 MAY 使用不同内部结构，只要满足上文 Normative Requirements。

```
DesiredState
  -> NormalizedState
  -> TargetSnapshot
  -> ReconcilePlan
  -> RuntimeSnapshot
  -> AgentProjection
```

### 5.1 Load DesiredState

从 `ComputerHome` 读取期望配置，例如 MCP Server、plugin、marketplace、SKILL exposure、tool policy、input definitions、connection config。

### 5.2 Normalize and Validate

把复杂配置规整成统一模型，并检查 schema、权限、冲突、策略和依赖。校验失败的对象进入 diagnostics，不进入成功的 target snapshot。

### 5.3 Build TargetSnapshot

生成 Computer 应达到的目标快照。TargetSnapshot 应尽量简单、稳定、可 diff，例如：

```text
MCP A: enabled, should_run
MCP B: disabled, should_stop
Plugin X: enabled
Skill foo: exposed
Tool browser.open: alias=open_browser, exposed
Tool shell.exec: forbidden
```

### 5.4 Diff Current vs Target

比较当前 runtime snapshot 与 target snapshot，生成需要执行的变更集合。协议不要求特定 diff 算法。

### 5.5 Apply ReconcilePlan

按依赖关系执行变更。一个常见顺序是：

1. stop / remove disabled things。
2. install / update packages。
3. start / update MCP Servers。
4. discover tools / resources / SKILLs / Desktop windows。
5. apply tool exposure policy。
6. apply SKILL exposure policy。

该顺序是非规范建议，不是 MUST。

### 5.6 Publish AgentProjection

根据实际成功的 runtime snapshot 生成 Agent-facing projection，并按变化发送 `server:update_*`。

AgentProjection SHOULD be derived from RuntimeSnapshot, not directly from raw DesiredState.
