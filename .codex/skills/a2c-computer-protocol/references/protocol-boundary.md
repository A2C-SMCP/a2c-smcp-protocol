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

## 保留为 SDK 指南

当某项行为有用但不是跨语言互操作所必需时，将其保留为实现指南：

- 本地 class、trait、method、callback 或 module layout。
- runtime 选择、任务模型、锁策略、进程组机制、重试调度器、watcher 实现、debounce 时长。
- 本地缓存编码、staging 目录结构、CLI 命令形状、settings 存储路径。
- 不影响协议可见字段的日志、诊断、指标、health checks 和 UX 流程。
- 让 SDK 更易用、但 Agent/Server 不依赖的 helper APIs。

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

## 兼容性标签

在协议草案中使用以下标签之一：

| 标签 | 含义 |
|---|---|
| Documentation-only | 澄清已有预期行为；预计无需 SDK 变更。 |
| Additive | 增加可选字段/事件/行为；旧 SDK 仍可互操作。 |
| Tightening | 将过去宽松的行为变为必需；可能需要 SDK conformance 修复。 |
| Breaking | 改变现有 wire shape，或拒绝过去可工作的行为。 |
| SDK guidance | 非规范性实现建议。 |

## 常见 Computer 边界陷阱

- 不要标准化 Python `async def` 或 Rust `async fn` 名称。应标准化 `client:*` 事件行为。
- 不要标准化 SKILL Home 路径，除非 Agent/Server 能看到它。应标准化路径不暴露、sandbox 和 `A2CSkillRef` 字段。
- 不要标准化 debounce 间隔。应标准化相关变更最终会在 Computer 位于 office 内时发送正确的 update notification。
- 不要标准化 blob handle 编码。应标准化不透明性、重新授权、chunk 语义、错误码和完整性字段。
- 不要标准化本地 input resolver 顺序，除非它影响协议可见的 config 值或 secret 暴露。
