# A2C-SMCP Protocol

<div class="grid cards" markdown>

-   :material-book-open-variant:{ .lg .middle } __协议规范__

    ---

    详细的协议规范文档，包括架构设计、事件定义、数据结构等

    [:octicons-arrow-right-24: 开始阅读](specification/index.md)

-   :material-source-branch:{ .lg .middle } __SDK 实现__

    ---

    官方 SDK 实现库

    - [Python SDK](https://github.com/A2C-SMCP/python-sdk) - Release Candidate
    - [Rust SDK](https://github.com/A2C-SMCP/rust-sdk) - 开发中

-   :material-help-circle:{ .lg .middle } __常见问题__

    ---

    关于协议设计决策的常见问题解答

    [:octicons-arrow-right-24: 查看 FAQ](appendix/faq.md)

</div>

## 什么是 A2C-SMCP

**A2C-SMCP**（Agent To Computer SMCP）是一种远程工具调用协议，定义了 Agent 与承载多路 MCP Server 的 Computer 之间的通信机制。该协议运行在 Socket.IO 之上，通过事件驱动的方式组织消息，并通过房间（Room/Office）机制实现安全隔离。

```
┌─────────┐         ┌─────────┐         ┌─────────┐
│  Agent  │ ←─────→ │  Server │ ←─────→ │Computer │
└─────────┘         └─────────┘         └─────────┘
   │                     │                   │
   │  工具调用发起方     │  信令服务器        │  MCP 服务管理者
   │                     │  连接管理          │  工具执行者
   │                     │  消息路由          │
   │                     │  通知广播          │
```

## 核心优势

| 特性 | 说明 |
|------|------|
| **工具热管理** | 动态发现/注册工具，配置热更新 |
| **安全隔离** | 基于房间的权限边界，Agent-Computer 绑定 |
| **网络穿透** | Socket.IO 长连接，免除公网 IP 依赖 |
| **弹性架构** | 多 Computer 支持，分布式工具部署 |
| **标准化接口** | 强类型数据结构，明确的事件边界 |

## 快速导航

- [协议概述](specification/index.md) - 了解设计目标与核心概念
- [架构设计](specification/architecture.md) - 深入理解三角色模型
- [事件定义](specification/events.md) - 完整的事件列表与规范
- [数据结构](specification/data-structures.md) - 请求/响应数据结构定义

## 版本信息

当前协议版本：**0.1.2-rc1**

## License

MIT License
