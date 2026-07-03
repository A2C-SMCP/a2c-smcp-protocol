# Inputs and Secrets Management

本文定义管理面如何处理 input 定义、用户填写值、secret store、env 文件和 OAuth 等本地授权状态。

## 1. 管理范围

本模块管理：

- input definition 与 resolved value 的边界。
- value cache、secret store、env file、OAuth 状态的管理面语义。
- list definitions / set value / clear value / test resolution / authorize / revoke。
- `client:get_config` 的安全投影。

本模块不管理：

- Agent-facing secret 传输；协议明确禁止该能力。
- MCP Server 具体启动状态，见 [MCP Server](mcp-server.md)。
- SKILL `.skillenv` 的包内读取规则，见 [SKILL Exposure](skill-exposure.md) 和 [SKILL 通道](../skill.md)。

## 2. 基本边界

Input definition 可以进入 Agent-facing `client:get_config`，但 resolved secret value MUST NOT 进入任何 Agent-facing 响应。

工具启动、MCP Server 连接、OAuth refresh 和本地脚本执行所需 secret MUST 在 Computer 本地解析。Agent 参数中的 token、secret、authorization code 或类似字段 MUST NOT 被视为可信凭据。

## 3. Operations

| 能力 | 语义 | Agent-facing 投影 |
|---|---|---|
| list input definitions | 列出本地 input 定义 | 非敏感定义 MAY 出现在 `client:get_config` |
| set input value | 写入用户填写值或 secret 引用 | 不暴露 resolved value |
| clear input value | 删除缓存值或 secret 引用 | 配置投影 MAY 变化 |
| test resolution | 管理面验证某配置是否可解析 | 不进入 Agent-facing 协议 |
| authorize provider | 完成本地 OAuth / device code 等授权 | 工具后续可本地使用凭据 |
| revoke provider | 删除或撤销本地授权 | 相关工具可能返回授权错误或变为不可用 |

## 4. 安全投影

`client:get_config` MAY 暴露 input id、描述、类型、是否必填、非敏感默认值或占位符信息。它 MUST NOT 暴露：

- API key / token / password。
- OAuth access token、refresh token、authorization code、code verifier。
- `.skillenv` 内容。
- secret store 内部路径或明文值。
- 本地 env file 的实际 secret 值。

Field-level projection follows [数据结构 §MCPServerInput](../data-structures.md#mcpserverinput):

| Field kind | Agent-facing rule |
|---|---|
| input id / type / description / required flag | MAY be exposed when needed for configuration discovery |
| enum options or non-secret defaults | MAY be exposed only when the value is not a credential or local secret |
| placeholder syntax such as `${input:id}` | MAY be exposed as an unresolved placeholder |
| resolved value cache | MUST NOT be exposed |
| env file contents, secret store location, keychain item id | MUST NOT be exposed |
| OAuth tokens, device codes, authorization codes, refresh metadata | MUST NOT be exposed |

Computer MUST NOT treat a token-like value supplied by Agent tool parameters as a trusted substitute for local secret resolution. If a tool requires credentials, those credentials must be obtained from Computer-local configuration or a trusted management action.

Input resolver order, cache lifetime, prompt UX, keychain provider, `.env` parser behavior and plugin-specific input prefixing are SDK guidance unless they change the Agent-facing `client:get_config` shape or leak secrets.
