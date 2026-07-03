# Management Security

本文定义 Computer Management Plane 的高权限安全边界。管理面可以控制本地 MCP Server、plugin、marketplace、SKILL 与 secret，因此必须与 Agent-facing 协议面隔离。

## 1. 管理范围

本模块管理：

- trusted local client 边界。
- 管理面访问保护责任。
- 管理诊断与 Agent-facing 响应隔离。
- marketplace / plugin source 信任策略。
- forbidden / disabled 能力的强制不可见与不可调用。

本模块不管理：

- Socket.IO Office 隔离细节，见 [房间隔离模型](../room-model.md)。
- Agent-facing secret 不传播原则的通用说明，见 [安全考虑](../security.md)。

## 2. 高权限边界

Computer Management Plane MUST 被视为高权限 surface。部署方 MUST 保护其访问边界，例如通过宿主应用权限、操作系统用户边界、本地认证、IPC 权限或平台私有控制面。

A2C-SMCP 不规定具体鉴权机制，但任何远程暴露的管理面都 MUST 有明确的认证和授权策略。

## 3. 诊断隔离

管理面 MAY 返回本地诊断、路径、日志、source URL、安装错误或策略拒绝原因。这些信息 MUST NOT 自动进入：

- `client:get_config`
- `client:get_tools`
- `client:get_skills`
- `client:get_skill`
- `client:get_blob`
- `client:get_desktop`
- tool metadata
- update notification

## 4. Source 信任

从 marketplace / plugin 安装的内容在暴露为 SKILL 或 MCP capability 前 SHOULD 经过本地策略校验。策略可以检查 source、签名、版本、兼容性、权限声明、allowed-tools 或组织规则。

策略拒绝的 source 或 plugin MUST NOT 暴露其能力给 Agent。

## 5. 禁用与移除

管理面禁用、forbid 或移除能力后，Computer MUST 尽快使 Agent-facing 能力不可见或不可调用。若旧工具调用已经在执行，终态仍必须遵守工具调用取消/失败的协议形状，且不得泄露管理面敏感诊断。

