# Management Errors

本文定义 Computer Management Plane 的错误类别与 Agent-facing 错误边界。管理面错误可以比 SMCP `ErrorPayload` 更丰富，但不自动进入 Agent-facing 协议。

## 1. 管理范围

本模块管理：

- 管理面错误类别。
- 管理诊断与 Agent-facing 错误的边界。
- partial failure 表达。
- retryability 与用户可修复性提示的分类。

本模块不管理：

- `client:*` flat `ErrorPayload` 全集，见 [错误处理](../error-handling.md)。
- MCP `CallToolResult.isError` 的工具级错误内容。

## 2. 错误类别

| 类别 | 示例 | Agent-facing 映射 |
|---|---|---|
| validation | 配置 schema 错误、plugin manifest 错误、SKILL frontmatter 错误 | 通常不映射 |
| conflict | 同名 MCP Server、工具 alias 冲突、SKILL name 冲突 | 通常不映射 |
| lifecycle | 启动失败、停止超时、健康检查失败、重连耗尽 | 能力可能不可见或不可调用 |
| authorization | marketplace 凭据失效、plugin source 无权限、OAuth 未完成 | 工具调用时可能体现为授权类工具错误 |
| policy | 工具被 forbidden、plugin 被组织策略禁止、source 不可信 | 能力 MUST 不可见或不可调用 |
| dependency | plugin 依赖缺失、运行时依赖缺失 | 通常不映射 |
| partial | 部分 reconcile 成功、部分失败 | 仅安全成功部分可投影 |

## 3. 诊断边界

管理面 MAY 返回本地路径、安装日志、source URL、manifest 片段或详细错误栈给可信管理员。Computer MUST NOT 自动把这些 diagnostics 放入 Agent-facing `ErrorPayload.details`、tool metadata、SKILL body 或 Desktop 内容。

只有当 Agent 调用 `client:*` 时，才使用 [错误处理](../error-handling.md) 定义的协议级错误或 MCP `CallToolResult.isError`。

## 4. Partial Failure

Partial failure SHOULD 明确列出：

- 成功应用的对象。
- 失败对象。
- 每个失败对象的错误类别。
- 是否需要重试。
- 是否已影响 Agent-facing 投影。

不可安全投影的对象 MUST 保持不可见或不可调用。

