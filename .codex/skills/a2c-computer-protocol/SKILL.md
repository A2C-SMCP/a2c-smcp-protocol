---
name: a2c-computer-protocol
description: 创建或修订语言无关的 A2C-SMCP Computer 侧协议规范。用于定义 Computer 行为、管理边界、生命周期要求、暴露给 Agent 的事件、MCP Server 管理语义、skill/blob/desktop/input/config 行为、取消/超时/错误契约，或在决定某项行为应写入协议还是作为 SDK 实现指南之前，对比现有 Python/Rust SDK 的 Computer 行为。
---

# A2C Computer Protocol

使用本 skill 编写 A2C-SMCP 的 Computer 侧协议文本。协议必须保持语言无关，并聚焦外部可观察行为：定义任何合规 Computer 必须做什么，而不是规定 Python、Rust、TypeScript 或其他 SDK 应如何组织类、trait、方法、任务或文件。

## 核心规则

写作前先区分三层：

1. **协议 MUST/SHOULD**：可观察的 wire 行为、请求/响应形状、事件发送、授权边界、Agent/Server 可见的生命周期状态，以及必要的错误语义。
2. **SDK 实现指南**：推荐的本地模块、缓存、watcher、进程监护、重试、文件系统布局、CLI UX 或辅助 API。
3. **参考实现细节**：Python/Rust 名称、函数签名、测试、注释和历史设计选择；它们可以作为行为依据，但不应被意外提升为协议义务。

## 工作流

1. 先阅读 `docs/specification/` 下的相关协议文档。从 `index.md`、`architecture.md`、`events.md`、`data-structures.md`、`error-handling.md` 开始，再阅读对应主题文档，例如 `skill.md`、`blob-transfer.md`、`desktop.md`、`room-model.md` 或 `security.md`。
2. 在形成结论前检查两个 SDK。默认参考路径为 `/Users/huruize/VSCodeProject/python-sdk` 和 `/Users/huruize/VSCodeProject/rust-sdk`；只有用户说明了其他 SDK 位置时才询问。
3. 使用 `references/sdk-evidence-map.md` 建立证据表。对比 Python 与 Rust 行为，并标记每项行为是共享、分歧、缺失，还是仅由测试暗示。
4. 使用 `references/protocol-boundary.md` 分类每条候选规则。只把语言无关且外部可观察的行为提升为协议文本。
5. 当 SDK 分歧，或现有行为过于实现相关、不能直接标准化时，使用 `references/discussion-template.md` 准备给用户的确认问题。
6. 用户确认后，按现有文档风格起草协议变更。优先新增或修订相关 `docs/specification/*.md` 页面，并交叉链接相关事件、数据结构和错误章节。
7. 检查每项新要求是否具备清晰的 consumer、producer、触发条件、成功形状、失败形状和兼容性影响。

## 必查主题

定义 Computer 行为时，必须显式考虑：

- **连接与房间成员关系**：Socket.IO namespace、版本握手预期、`auth.role=computer`、office join/leave、单 office 绑定、Server/Agent 可见的重连行为。
- **MCP Server 管理**：server config 接收、start/stop/update/remove 语义、工具发现、重复工具处理、alias/disabled/forbidden-tool 行为，以及可观察的 health/reconnect 行为。
- **面向 Agent 的事件 handler**：`client:tool_call`、`client:get_tools`、`client:get_config`、`client:get_desktop`、`client:get_resources`、`client:get_skills`、`client:get_skill` 和 `client:get_blob`。
- **通知**：Computer 何时必须发送 `server:update_config`、`server:update_tool_list`、`server:update_desktop` 和 `server:update_skills`；除非协议需要可观察保证，否则 debounce/coalescing 只作为 SDK 指南。
- **工具执行**：目标路由、超时、取消、`CallToolResult` 错误元数据、二进制结果旁路，以及仅在影响 desktop 排序或其他可观察行为时才纳入的工具调用历史。
- **Desktop 聚合**：`window://` 过滤、读取/渲染规则、size/window 参数、priority/fullscreen/audience 处理、基于历史的排序。
- **SKILL 管理**：source 模型、name lexer、Agent 可见的 staging 结果、`get_skills`/`get_skill`、sandbox、orphan 处理、更新通知。
- **Blob 传输**：handle 不透明性、chunk offset、背压、sha256/size 稳定性、range 错误、拉取时重新授权。
- **Inputs 与 secrets**：仅本地解析、占位符渲染语义、value cache 可见性、`.skillenv` 与凭据不暴露。
- **Settings/config**：哪些配置通过 `client:get_config` 协议可见，哪些属于本地 SDK/CLI policy。
- **安全**：房间隔离、禁止任意文件读取、禁止向 Agent 传播凭据、安全的错误 details、能力边界。

## 写作规则

- 仅对具有可测试、可观察结果的协议义务使用 RFC 2119 关键字。
- 优先写 "Computer MUST respond with..." 或 "Computer MUST NOT expose..."，避免 "the SDK should call..." 或 "the manager should store..." 这类实现表述。
- 不要要求特定本地路径、类名、trait、线程模型、async runtime、进程模型、缓存编码或 CLI 命令，除非协议 wire 契约确实依赖它。
- 当某项行为只存在于一个 SDK、另一个 SDK 没有时，把它写成开放决策，并在标准化前询问用户。
- 当两个 SDK 出于工程原因共享某项行为，但该行为不可由外部观察时，将其记录为非规范性实现指南，或直接不写入协议。
- 保留现有 A2C 术语：Agent、Server、Computer、Office/Room、MCP Server、Desktop、SKILL、BlobHandle。
- JSON 示例保持语言无关。除非明确需要 reference implementation note，否则使用 JSON、表格和 sequence diagram，而不是 Python/Rust 示例。

## 交付物

对于较大的协议工作，按顺序产出：

1. **证据摘要**：检查过的 SDK 路径、共享行为、分歧和不清楚的区域。
2. **决策问题**：当协议意图尚不明确时，给用户的简洁选项。
3. **协议草案**：具体 Markdown 编辑或拟议章节，使用 MUST/SHOULD/MAY 表述。
4. **兼容性说明**：变更是 additive、tightening、breaking 还是 documentation-only。
5. **验证清单**：应更新的事件、数据结构、错误和 SDK conformance tests。

## 参考

- `references/sdk-evidence-map.md`：如何检查 Python/Rust SDK 行为并汇总证据。
- `references/protocol-boundary.md`：如何判断协议、SDK 指南和参考实现细节的边界。
- `references/discussion-template.md`：在最终确定 Computer 行为前，如何组织面向用户的决策讨论。
