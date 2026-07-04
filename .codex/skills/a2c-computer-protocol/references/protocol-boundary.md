# 协议边界指南

使用本指南判断哪些内容属于 A2C-SMCP 协议文本。

## 提升为协议

满足以下任一条件时，将行为提升为协议：

- Agent、Server 或另一个 SDK 能在 wire 上观察到该行为。
- 如果两个 Computer SDK 选择不同行为，互操作性会被破坏。
- 它约束安全、授权、房间隔离、文件访问、凭据传播或错误泄露。
- 它定义请求/响应字段、事件名、ack 语义、超时/取消状态或错误 payload 形状。
- 它定义 Computer 外部可见的生命周期状态，例如加入/离开房间或发送更新通知。
- 它定义资源身份、name lexer、URI 语义或 blob handle 语义。

## 提升为 Computer Runtime Contract

当行为不是 wire protocol，但业务 client 需要跨 SDK 稳定依赖时，将其写入 Computer Runtime Contract：

- 同一份 `ComputerConfig` 和 `RuntimeOptions` 在 Python/Rust/TypeScript SDK 中解析为等价 runtime intent。
- SDK 提供从声明式 config 创建单个 runtime Computer 的稳定语义。
- `start`、`stop`、`connect`、`disconnect`、`sync_config`、`shutdown` 等公共能力的效果和状态迁移需要跨 SDK 一致。
- 默认值、错误分类、retryability、生命周期状态、marketplace/plugin 挂载规则和 shutdown 释放语义需要一致。
- 同一批 JSON fixture 和生命周期场景应能作为 SDK conformance tests。

Runtime Contract 不要求各 SDK 使用相同代码形态。Builder、factory、constructor、async constructor、dataclass、trait、锁、runtime、缓存和目录布局仍属于 SDK 自由。

## 保留为 SDK 指南

当某项行为有用但不是跨语言互操作所必需时，将其保留为实现指南：

- 本地 class、trait、method、callback 或 module layout。
- runtime 选择、任务模型、锁策略、进程组机制、重试调度器、watcher 实现、debounce 时长。
- 本地缓存编码、staging 目录结构、CLI 命令形状、settings 存储路径。
- 不影响协议可见字段的日志、诊断、指标、health checks 和 UX 流程。
- 让 SDK 更易用、但 Agent/Server 不依赖的 helper APIs。

SDK 指南必须标记为非规范性。它可以解释推荐抽象、测试入口、迁移策略和工程取舍，但不得改变协议义务的范围。

好的 SDK 指南通常满足以下条件：

- 明确说明它服务的协议目标，例如事件一致性、安全隔离、错误稳定性或开发者体验。
- 给出可移植的实现建议，而不是绑定 Python/Rust/TypeScript 的类名、trait、函数签名或 runtime。
- 说明哪些选择可以由 SDK 自行决定，例如 debounce 时长、缓存编码、watcher 实现和 CLI 交互。
- 指向 SDK conformance checklist 中对应的可测试协议行为或 runtime contract 行为。

## 保留为 Client 责任

当行为属于真实业务 client 的产品编排，而不是单个 Computer runtime 的稳定语义时，保留在 client 层：

- 管理多个 Computer。
- 持久化用户或 workspace 配置。
- 管理 UI 状态、账号选择、Manager/Server/office 选择和用户连接策略。
- 管理敏感信息存储和用户操作审计。
- 编排多个 runtime 的生命周期，除非 SDK 明确标准化更高层 `ComputerManager`。

## 保留为参考细节

当某项行为是偶然的或范围过窄时，不写入协议：

- 针对单个语言库的 workaround。
- 历史函数名或注释。
- 不代表真实协议契约的测试 fixture 形状。
- 当前 SDK bug、未完成实现或临时 milestone 说明。

## 规范性措辞检查清单

写 `MUST` 前确认：

- 谁必须执行：Computer、Server、Agent 还是 MCP Server。
- 何时适用：事件、状态、source、参数条件、错误条件。
- 可观察结果是什么：响应字段、通知、不暴露、错误码、metadata key。
- 如何在不检查私有内部状态的情况下测试合规实现。
- 现有 Python 和 Rust SDK 是否已经符合；如果不符合，记录兼容性影响。

## Runtime Contract 检查清单

写 Computer Runtime Contract 前确认：

- 业务 client 是否需要跨 SDK 依赖该语义。
- 如果 Python/Rust SDK 行为不同，是否会导致同一个 Manager、Agent、Computer、marketplace、plugin、skill、tool 或 MCP server 运行时表现不同。
- 该要求是否描述公共 SDK 行为，而不是语言专属调用形态。
- 是否能用同一批 JSON fixture、生命周期场景、公共 SDK 返回值、公开事件或错误分类验证。
- 是否清楚区分单个 Computer runtime 责任和 client 多实例编排责任。

## SDK 指导检查清单

写 SDK guidance 前确认：

- 这条建议是否确实帮助 SDK 实现某个协议义务，或提升 SDK 作者的开发体验。
- 它是否保持 non-normative，没有使用 `MUST` 规定本地内部结构。
- 它是否避免语言专属 API、路径、runtime、进程模型、缓存格式和 CLI 形状。
- 它是否说明哪些部分是推荐做法，哪些部分只是参考实现当前选择。
- 它是否能转化为 SDK conformance test、SDK unit test 或迁移检查项。

写 SDK conformance checklist 前确认：

- 每一项都能从 wire 行为、公开响应、公开事件、错误 payload 或安全边界验证。
- 每一项都有明确的触发条件和期望结果。
- 每一项不要求测试私有字段、内部缓存、线程模型或具体代码结构。
- checklist 覆盖新增的 MUST/SHOULD，并标明 MAY 项是否需要兼容性测试。

## 兼容性标签

在协议草案中使用以下标签之一：

| 标签 | 含义 |
|---|---|
| Documentation-only | 澄清已有预期行为；预计无需 SDK 变更。 |
| Additive | 增加可选字段/事件/行为；旧 SDK 仍可互操作。 |
| Tightening | 将过去宽松的行为变为必需；可能需要 SDK conformance 修复。 |
| Breaking | 改变现有 wire shape，或拒绝过去可工作的行为。 |
| Runtime-contract | 定义或收紧公共 SDK 语义；需要共享 fixture 或 lifecycle conformance tests。 |
| SDK guidance | 非规范性实现建议。 |

## 常见 Computer 边界陷阱

- 不要标准化 Python `async def` 或 Rust `async fn` 名称。应标准化 `client:*` 事件行为。
- 不要标准化 SKILL Home 路径，除非 Agent/Server 能看到它。应标准化路径不暴露、sandbox 和 `A2CSkillRef` 字段。
- 不要标准化 debounce 间隔。应标准化相关变更最终会在 Computer 位于 office 内时发送正确的 update notification。
- 不要标准化 blob handle 编码。应标准化不透明性、重新授权、chunk 语义、错误码和完整性字段。
- 不要标准化本地 input resolver 顺序，除非它影响协议可见的 config 值或 secret 暴露。
