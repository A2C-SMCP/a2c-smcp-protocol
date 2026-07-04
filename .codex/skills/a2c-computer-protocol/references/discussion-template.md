# 讨论模板

当 SDK 证据无法直接决定 Computer 协议行为时，使用本模板。

## 决策简报

```markdown
**主题**：<简短主题>

**当前协议**：
- <当前文档如何描述，带文件引用>

**SDK 证据**：
- Python：<行为和源路径>
- Rust：<行为和源路径>

**互操作风险**：
- <如果 SDK 行为不同会破坏什么>

**推荐协议立场**：
- <MUST/SHOULD/MAY、SDK guidance，或保持未规定>

**需要用户决策**：
1. <选项 A 及其后果>
2. <选项 B 及其后果>
3. <延后决策及其后果>
```

## 要问的问题

优先询问具体协议问题：

- "这应该是可观察的协议行为，还是只作为 SDK guidance？"
- "如果 Python 和 Rust 分歧，哪个行为应成为 canonical？"
- "不符合要求的输入应该返回 flat `ErrorPayload`、MCP `CallToolResult.isError`，还是 no-op？"
- "这个行为应该立即成为必需，还是先文档化为未来 conformance target？"
- "这是语言无关的设计意图，还是仅仅是 reference SDK convenience？"

避免模糊问题：

- "这样可以吗？"
- "要支持这个吗？"
- "你喜欢这个设计吗？"

## 协议草案骨架

````markdown
### <行为名称>

Computer MUST/SHOULD/MAY <可观察行为> when <条件>。

Request:
```json
{ "...": "..." }
```

Success response:
```json
{ "...": "..." }
```

Failure:

| Condition | Response |
|---|---|
| <condition> | <flat ErrorPayload or CallToolResult shape> |

Notes:

- <必要时填写非规范性 SDK guidance>
- <compatibility label>
````

## 最终审查清单

- 确认每个字段都使用现有 `snake_case` 风格。
- 确认 flat `ErrorPayload` 没有被包成 `{"error": ...}`。
- 确认工具执行失败时 `CallToolResult` 仍保持 MCP 形状。
- 确认敏感 details 不会进入 `details`。
- 确认没有意外把本地路径、class、trait 或 runtime 写成规范要求。
- 确认文档已交叉链接相关事件、数据结构、错误和安全章节。
