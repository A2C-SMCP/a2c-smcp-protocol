# Computer 侧协议框架

本文定义 A2C-SMCP 中 Computer 的外部可观察行为框架。它把现有事件、数据结构、Desktop、SKILL、Blob、房间与安全章节串成一个合规边界；具体字段与错误码仍以被链接的主题章节为准。

## 1. 范围与边界

Computer 是 Agent 与一个或多个 MCP Server 之间的协议桥。合规 Computer 的协议职责是：

1. 以 `auth.role = "computer"` 连接 `/smcp` 命名空间，并通过 `server:join_office` 加入一个 Office。
2. 接收 Server 路由的 `client:*` 事件，执行本地 MCP / SKILL / Blob / Desktop 行为，并在 ack 通道返回成功响应或协议级错误。
3. 在自身可见能力发生变化时，通过 `server:update_*` 事件请求 Server 向 Office 广播 `notify:update_*`。
4. 持有 MCP Server 凭据与本地资源访问权，但不得把凭据或任意文件读能力暴露给 Agent。

本页不规定本地 class、trait、线程模型、进程监护、缓存布局、文件 watcher、debounce 时间、CLI UX 或 SDK helper API。只要 wire 行为、事件、响应、错误与安全边界一致，实现可以自由选择内部结构。

可信本地客户端若需要管理 MCP Server 启停、SKILL 暴露、marketplace 或 plugin，应使用独立的 [Computer Management Plane](computer-management/index.md)。该管理面修改 Computer desired state；本页只规定这些修改完成后 Agent 可观察的协议投影。

## 2. 生命周期

### 2.1 连接

Computer MUST 按 [事件定义 §连接握手](events.md#连接握手) 携带 `a2c_version` URL query，并在 Socket.IO `auth` 对象中声明：

```json
{ "role": "computer" }
```

Computer MAY 在 `auth` 中携带业务鉴权字段。协议不规定这些字段的名字、位置或认证算法，但 Computer SDK MUST NOT 把 MCP Server 凭据、`.skillenv` 内容或其它本地 secret 放入 `auth`。

### 2.2 加入与离开 Office

Computer MUST 使用 `server:join_office` 发送 `EnterOfficeReq`，其中 `role` MUST 为 `"computer"`，`name` 是该 Computer 在 Server 路由中的标识。Server 负责单 Office 绑定与跨房间隔离，见 [房间隔离模型](room-model.md)。

Computer SHOULD 在成功加入 Office 后才发送 `server:update_config`、`server:update_tool_list`、`server:update_desktop` 或 `server:update_skills`。未加入 Office 时，本地变化可以被记录或合并，但不应产生跨房间可见通知。

Computer 离开 Office 或断连后，Server MUST 停止向该 Computer 路由新的 `client:*` 事件。Computer 对已转发且仍在执行的工具调用是否继续运行属于本地副作用策略；若能返回原 ack，则终态仍 MUST 使用本协议定义的 `CallToolResult` 形状。

## 3. Agent 可调用事件面

Computer MUST 实现下列 Server 路由来的 `client:*` 事件：

| Event | Computer 行为 | 成功响应 | 失败响应 |
|---|---|---|---|
| `client:tool_call` | 路由到目标 MCP Server 工具并执行 | MCP `CallToolResult` | 工具失败仍为 `CallToolResult.isError=true` |
| `client:get_tools` | 返回当前可用工具聚合视图 | `GetToolsRet` | flat `ErrorPayload` |
| `client:get_config` | 返回 Agent 可见配置 | `GetComputerConfigRet` | flat `ErrorPayload` |
| `client:get_desktop` | 返回 `window://` 聚合 Desktop | `GetDeskTopRet` | flat `ErrorPayload` |
| `client:get_resources` | 透明转发指定 MCP Server 的 `resources/list` | `GetResourcesRet` | `4014` / `4015` flat `ErrorPayload` |
| `client:get_skills` | 返回当前活跃 SKILL 元数据清单 | `GetSkillsRet` | flat `ErrorPayload` |
| `client:get_skill` | 返回单个 SKILL 包内资源 | `GetSkillRet` | `4016` / `4014` / `4017` flat `ErrorPayload` |
| `client:get_blob` | 按 `blob_handle` 分块拉取字节 | `GetBlobRet` | `4018` flat `ErrorPayload` |

所有 `client:*` 事件中的 `computer` 字段 MUST 与接收方 Computer 的协议名一致。不一致时 Computer MUST NOT 执行目标行为；实现可以返回协议级错误或让路由层失败。Server 仍 MUST 执行同房间路由校验，Computer 侧校验只是防御纵深。

除 `client:tool_call` 的工具级失败外，协议级错误 MUST 使用 [错误处理 §错误响应格式](error-handling.md#错误响应格式) 的 flat `ErrorPayload`，不得包装为 `{"error": ...}`。

## 4. MCP Server 管理

Computer 负责把本地 MCP Server 配置转化为 Agent 可见的工具、资源和窗口视图。

### 4.1 配置可见性

`client:get_config` MUST 返回 Agent 可以安全观察的 `servers` 与 `inputs` 结构。Computer MUST NOT 在响应中展开 secret 值、`.skillenv` 内容、OAuth token、API key、环境变量实际值或本地凭据文件内容。

输入占位符、env 文件、secret store、value cache 的解析顺序属于 SDK guidance；协议只要求最终 wire 响应不泄露凭据，且工具启动时所需 secret 仅在 Computer 本地解析。

### 4.2 工具列表

Computer MUST 从已启用且可用的 MCP Server 收集工具并返回 `SMCPTool`。当工具需要附加 A2C 元数据时，Computer MUST 使用 [SMCPTool.meta 序列化规范](data-structures.md#smcptoolmeta-序列化规范)，把复杂结构放在 `meta["a2c_tool_meta"]` JSON 字符串中。

当不同 MCP Server 暴露同名工具时，Computer MUST 保证 Agent 看到的工具名可路由到唯一目标，或通过禁用 / 别名 / 配置拒绝使冲突不可见。具体冲突解决 UX 属 SDK guidance；可观察结果不能让同一个 `tool_name` 随机路由到不同 MCP Server。

### 4.3 资源透明转发

`client:get_resources` 是指定 MCP Server 的单页 `resources/list` 透明转发。Computer MUST NOT 按 scheme、`_meta`、`annotations` 或内容过滤该响应，也 MUST NOT 做跨 Server 聚合。未知 `mcp_server` MUST 返回 `4014`；目标 MCP Server 未声明 `resources` capability MUST 返回 `4015`。

### 4.4 MCP Server 生命周期

Computer MAY 支持在运行中新增、更新、禁用或移除 MCP Server。协议不规定这些操作的本地入口，但一旦操作完成，Agent 可见状态 MUST 与新配置一致：

1. 新增或重新启用 MCP Server 后，其可见工具、资源、窗口与 SKILL SHOULD 能通过对应 `client:get_*` 事件发现。
2. 更新 MCP Server 配置后，旧配置中不再可用的工具、资源、窗口与 SKILL MUST NOT 继续作为可调用能力暴露。
3. 禁用或移除 MCP Server 后，Computer MUST NOT 执行该 Server 的工具；相关工具 MUST 从后续 `client:get_tools` 响应中消失，相关 MCP source SKILL MUST 从后续 `client:get_skills` 响应中消失或被标记为不可见孤儿。
4. 被配置为 disabled 或 forbidden 的工具 MUST NOT 出现在可调用工具列表中，也 MUST NOT 被 `client:tool_call` 成功执行。
5. 当生命周期变化影响 Agent 可见状态时，Computer SHOULD 发送相应 `server:update_config`、`server:update_tool_list`、`server:update_desktop` 或 `server:update_skills`。

进程启动方式、重启策略、健康检查周期、自动重连、退避算法与本地错误恢复属于 SDK guidance；协议只规定变化完成后的可见状态和通知义务。

## 5. 工具执行、取消与二进制结果

`client:tool_call` MUST 返回 MCP `CallToolResult`。工具自身失败、上游执行失败、授权失败、超时与取消都不得改变 `CallToolResult` 的基本 MCP 形状。

Computer SHOULD 在工具调用超时时尝试中断底层执行，并在结果级 `meta` 写入 `a2c_timeout = true`。Agent 发出的 `server:tool_call_cancel` 经 Server 广播为 `notify:tool_call_cancel`；Computer 收到后 MUST 按 `req_id` 尝试取消本机在途调用。未知或已完成的 `req_id` MUST 作为幂等 no-op 处理，不返回错误。

取消成功时，原 `client:tool_call` 的 ack MUST 返回 `CallToolResult(isError=true)`，并在结果级 `meta` 写入 `a2c_cancelled = true`，SHOULD 写入 `a2c_cancel_reason = "agent_requested"`。

当 `CallToolResult` 中的二进制 content item 超过内联预算时，Computer MUST 按 [通用二进制传输 §生产者通道接入契约](blob-transfer.md#5-生产者通道接入契约) 铸造 `blob_handle`，在 content item `_meta` 写入 `a2c_blob_handle`、`a2c_total_size`、`a2c_sha256`，并清空该 item 的内联字节载体。小尺寸二进制 MAY 保持内联。

## 6. Desktop 通道

Computer MUST 把 MCP Server 暴露的 `window://` Resource 聚合为 Desktop，行为见 [Desktop 桌面系统](desktop.md)。

框架层要求如下：

1. `client:get_desktop` 未带 `window` 时返回聚合视图；带 `window` 时按完整 URI 字符串精确匹配。
2. Computer MUST 跳过无效 `window://` URI、空内容窗口以及当前无法渲染的纯 Blob 窗口。
3. Computer MUST 使用 Resource `annotations.priority` 与 `_meta.fullscreen` 的协议语义组织结果。
4. 当窗口集合或内容发生变化且 Computer 已在 Office 内时，Computer SHOULD 发送 `server:update_desktop`。

资源缓存、订阅管理、debounce 与读取失败重试属于 SDK guidance。

## 7. SKILL 通道

Computer 是 SKILL 管理者。它 MUST 对 Agent 暴露统一的 `A2CSkillRef` 清单与单资源读取接口，而不要求 Agent 理解 source 的本地物化细节。

框架层要求如下：

1. `client:get_skills` MUST 只返回活跃、已物化、可用的 SKILL；孤儿 SKILL MUST 被排除。
2. `client:get_skill` MUST 先校验 name lexer；非法 name 返回 `4016`。
3. 合法但未注册、已卸载或已孤儿的 name MUST 返回 `4014`，并把 name 放入 `details`。
4. `rel_path` MUST 限制在 SKILL 包根内；路径穿越、`.skillenv`、凭据类文件、包内不存在或超过生产者上限 MUST 返回 `4017`。
5. 成功时 `body` 与 `blob_handle` MUST 恰一存在；二进制或过大文本 MUST 转 `client:get_blob`。

SKILL Home 路径、marketplace 安装 UX、文件 watcher、staging 目录布局、孤儿清理时机属于 SDK guidance；Agent 可见行为以 [SKILL 通道](skill.md) 为准。

## 8. Blob 通道

Computer MUST 实现 `client:get_blob`。`blob_handle` 对 Agent 是不透明能力引用；Agent MUST NOT 解析、拼接、伪造或跨 Computer 复用。

Computer 每次处理 `client:get_blob` 时 MUST：

1. 解析句柄并识别生产者通道。
2. 重施铸造通道的授权与边界校验。
3. 使用资源字节的绝对 `chunk_offset` 切片。
4. 返回全量 `total_size` 与 `sha256`，并把本块字节 base64 放入 `blob`。
5. 对无效句柄、重施鉴权失败、源消失或范围错误返回 `4018`。

Computer MUST NOT 把 `client:get_blob` 实现为任意本地文件读取接口。

## 9. 更新通知

Computer 在可见状态变化后 SHOULD 使用下列表达式通知 Server；Server 再广播对应 `notify:*`：

| Computer 触发 | Server 广播 | 典型触发 |
|---|---|---|
| `server:update_config` | `notify:update_config` | MCP Server 配置或 Agent 可见 inputs 变化 |
| `server:update_tool_list` | `notify:update_tool_list` | 工具集合、别名、禁用状态或元数据变化 |
| `server:update_desktop` | `notify:update_desktop` | `window://` 集合或内容变化 |
| `server:update_skills` | `notify:update_skills` | SKILL 集合、frontmatter 或可读资源变化 |

协议不规定 debounce/coalescing 时间。合规实现可以合并多次本地变化，但 SHOULD 保证 Agent 最终能通过对应 `client:get_*` 拉到新状态。

## 10. 安全不变量

Computer MUST 遵守下列安全不变量：

1. 不向 Agent 传播 MCP Server token、OAuth credential、API key、`.skillenv`、用户密码或本地 secret store 值。
2. 不允许 Agent 通过 SKILL / Blob / Desktop / Resource 通道读取任意本地文件。
3. 不信任 `blob_handle` 内部内容；句柄解析后仍必须重新执行源通道边界校验。
4. 不把敏感信息放入 `ErrorPayload.details`、工具错误文本或 update notification。
5. 不绕过 Server 房间隔离；任何可见状态都必须限定在当前 Office 路由内。

## 11. 非规范性 SDK 证据摘要

本框架参考了以下实现路径：

| 主题 | Python SDK | Rust SDK | 结论 |
|---|---|---|---|
| `client:*` handler | `a2c_smcp/computer/socketio/client.py` | `crates/smcp-computer/src/socketio_client.rs` | 事件面基本共享 |
| SKILL registry / sandbox | `a2c_smcp/computer/skills/*` | `crates/smcp-computer/src/skills/*` | 4016/4017/孤儿排除共享 |
| Blob handle / resolver | `a2c_smcp/computer/blob/*` | `crates/smcp-computer/src/blob/*` | 4018 与重施鉴权共享 |
| Desktop organize | `a2c_smcp/computer/desktop/*` | `crates/smcp-computer/src/desktop/*` | `window`、priority、fullscreen 语义共享 |
| 取消 / 超时 | `Computer.aexecute_tool` / `acancel_tool` | `Computer::execute_tool_cancellable` | `a2c_cancelled` / `a2c_timeout` 共享 |

这些路径只作为行为证据，不把其中的 class、trait、锁、缓存或本地路径提升为协议义务。
