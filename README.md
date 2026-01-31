# A2C-SMCP Protocol Specification

A2C-SMCP (Agent To Computer SMCP) 是一种远程工具调用协议，定义了 Agent 与 Computer 之间通过 Socket.IO 进行通信的规范。

## 文档结构

- [协议概述](specification/index.md) - 设计目标与核心概念
- [架构设计](specification/architecture.md) - 角色关系与通信模型
- [事件定义](specification/events.md) - 完整事件列表
- [数据结构](specification/data-structures.md) - 请求/响应数据结构
- [房间模型](specification/room-model.md) - 房间隔离机制
- [错误处理](specification/error-handling.md) - 错误码与响应格式
- [安全考虑](specification/security.md) - 安全性要求
- [FAQ](appendix/faq.md) - 常见问题

## SDK 实现

| 语言 | 仓库 | 状态 |
|------|------|------|
| Python | [python-sdk](https://github.com/A2C-SMCP/python-sdk) | RC |
| Rust | [rust-sdk](https://github.com/A2C-SMCP/rust-sdk) | 开发中 |

## 版本

当前协议版本: **0.1.2-rc1**

## License

MIT
