# DPE 模块移除变更报告

> **决议日期**：2026-05-08
> **影响版本**：a2c-smcp-protocol v0.2.0（移除前为 candidate 状态）
> **目标读者**：python-sdk / rust-sdk 实现团队、Computer / Agent / MCP Server 业务方
> **关联仓库**：DPE 协议已独立到 [github.com/A2C-SMCP/dpe-protocol](https://github.com/A2C-SMCP/dpe-protocol)

---

## 1. 决议摘要

A2C-SMCP v0.2 早期草案曾把 **DPE（Document-Page-Element）** 作为内嵌资源类型（`dpe://` URI + `client:get_dpe` + Resolver Hook + 双 mimetype），后判断 DPE 与 A2C-SMCP 控制面属性不匹配——因此**从 A2C-SMCP 协议中整体移除**，独立为单独的 [dpe-protocol](https://github.com/A2C-SMCP/dpe-protocol) 仓库。

### 移除原因

1. **数据流方向不对**：DPE 真实数据流是 User → Agent，而 A2C-SMCP 是 Agent → Computer 控制面。Agent 不是发起者，而是被动消费 User 已经准备好的内容。
2. **传输形态不匹配**：DPE 文档（PPT / Word / Excel / PDF 解析后）体量从 KB 到几百 MB；硬塞进控制面 Socket.IO 通道，无论如何都需要应用层重做 transport（chunk / 流控 / 重传），这本应是 transport 层职责。
3. **业界先例齐全**：Kubernetes API ↔ Container Registry、Helm CLI ↔ OCI Registry、HuggingFace Inference API ↔ HuggingFace Hub——控制面与数据面历来都是独立协议。

### 演进后的两层职责

| 层 | 协议 | 职责 |
|---|------|------|
| 控制面 | **A2C-SMCP** | 工具调用、Computer 配置、Desktop（Window URI）、资源发现（透明转发） |
| 数据面 | **DPE Protocol**（独立仓库）| 基于 OCI Distribution 的内容寻址 + 增量分发；Document / Page / Element 三层 Merkle 树字节投递 |

A2C-SMCP 协议层**不再涉及任何 DPE 字节投递**。

---

## 2. 已删除的协议表面

### 2.1 事件（client:* 层）

| 事件 | 状态 | 说明 |
|------|------|------|
| `client:get_dpe` | ❌ **完全删除** | 不再存在；SDK 应移除其类型定义 / 事件处理 / 测试 |
| 关联类型 `GET_DPE_EVENT` | ❌ 删除 | 事件常量表中移除 |

> **保留**：`client:get_resources`（透明转发 MCP `resources/list`）继续保留，用于 Window 等其他资源发现场景。

### 2.2 错误码

| 码 | 名称 | 状态 |
|----|------|------|
| 4011 | DPE Resolver Not Configured | ❌ **完全删除** |
| 4012 | Invalid DPE URI | ❌ **完全删除** |
| 4013 | DPE Resolution Failed | ❌ **完全删除**（含 `category` 字段及 4 个枚举值）|
| 4201 | Document Not Found | ❌ **删除**（Finder 子系统已废弃）|
| 4202 | Page Out of Range | ❌ **删除** |
| 4203 | Element Not Found | ❌ **删除** |
| 4204 | Invalid DPE URI | ❌ **删除** |

### 2.3 数据结构（TypedDict / Pydantic Model）

| 类型 | 状态 |
|------|------|
| `GetDPEReq` | ❌ 删除 |
| `GetDPERet` | ❌ 删除 |
| `ResolverContents`（Union）| ❌ 删除 |
| `InlineContents` | ❌ 删除 |
| `ExternalContents` | ❌ 删除 |
| `ResolverHint` | ❌ 删除 |

> **保留**：`A2CResource` / `GetResourcesReq` / `GetResourcesRet` 继续保留——它们用于通用 Resource 发现，不再与 DPE 绑定。

### 2.4 业务回调 / Hook

| 接口 | 状态 |
|------|------|
| **DPE Resolver Hook**（业务层注册回调）| ❌ **完全删除** |
| Resolver 注册 API（`register_dpe_resolver` 等命名）| ❌ 删除 |

业务方**不再需要**实现 DPE Resolver——所有 DPE 内容投递改由 Computer **不参与**，由 Agent 直接通过独立的 dpe-protocol 客户端拉取。

### 2.5 MIME Types

| 字符串 | 状态 |
|--------|------|
| `application/vnd.a2c.dpe-inline+json` | ❌ 删除 |
| `application/vnd.a2c.dpe-uri+json` | ❌ 删除 |
| `application/vnd.a2c.dpe.doc.v1+json` | ⚠️ **迁出** | dpe-protocol 仓库使用，不再属 A2C-SMCP |

### 2.6 URI Scheme

| Scheme | 状态 |
|--------|------|
| `dpe://...` | ⚠️ **迁出** | A2C-SMCP 协议层不再识别；dpe-protocol 仓库使用 |
| `window://...` | ✅ 保留 | A2C-SMCP 控制面继续使用 |

A2C-SMCP 协议层**不再**对 `dpe://` URI 做任何处理（不路由、不解析、不验证）。如 Agent 拿到 dpe URI，应直接用 dpe-protocol 客户端拉取，与 A2C-SMCP Server 无关。

### 2.7 host 唯一性约束变化

| 项 | v0.2 草案 | v0.2 当前 |
|----|----------|-----------|
| host 跨 Server | **MUST** 唯一（注册阻塞）| **SHOULD** 唯一（lint-style WARN，不阻塞） |

理由：MUST 约束的原始动机是 `client:get_dpe` 通过 host 反查 MCP Server 路由——该事件已删除，host 唯一性不再需要硬约束。

---

## 3. 文档变更详表

### 3.1 整体删除（3 个文件）

- `docs/specification/dpe.md`
- `docs/specification/dpe-merkle-transport.md`
- `docs/specification/dpe-standardization-proposal.md`

### 3.2 大幅修改

- `docs/migrations/v0.2-uri-metadata-refactor.md` —— 整体重写，**保留**非 DPE 改动（Window URI / 协议版本握手 / 错误码 4006/4007/4008/4014/4015 / priority 类型）

### 3.3 小幅修改（删除 DPE 嵌入段落）

- `docs/specification/events.md` —— 删除 `client:get_dpe` 完整定义、DPE 流程图、Agent 流程示例中的 DPE 步骤
- `docs/specification/error-handling.md` —— 删除 4011/4012/4013 详细章节、DPE 资源访问错误段、Finder 错误码
- `docs/specification/data-structures.md` —— 删除 `GetDPEReq` / `GetDPERet` / `ResolverContents` / `ResolverHint`；将"DPE 文档相关结构"小节改名为"Resource 发现相关结构"
- `docs/specification/architecture.md` —— 删除"DPE 文档抽象"整章及 ASCII 图
- `docs/specification/desktop.md` —— 删除 host 共享命名空间相关 DPE 链接，hard MUST 改为 SHOULD
- `docs/specification/versioning.md` —— 移除 `dpe://` URI scheme 示例
- `docs/specification/index.md` —— 移除 DPE 文档协议入口
- `docs/appendix/faq.md` —— 删除"DPE 文档相关"FAQ（8 问），改为一段简短的历史背景
- `mkdocs.yml` —— nav 移除 DPE 入口

### 3.4 dpe-protocol 仓库迁入

| 来源（已删除） | 目标 |
|-------------|------|
| `dpe-merkle-transport.md` | [`dpe-protocol/docs/merkle-hash-spec.md`](https://github.com/A2C-SMCP/dpe-protocol/blob/main/docs/merkle-hash-spec.md) |
| `dpe-standardization-proposal.md` | [`dpe-protocol/docs/data-model.md`](https://github.com/A2C-SMCP/dpe-protocol/blob/main/docs/data-model.md) |

哈希算法规范（§3）、19+ 元素类型 schema、30+ 文档格式映射等核心规范全部完整保留在 dpe-protocol 仓库，可作为 SDK 实现的权威源。

---

## 4. 客户端开发计划影响

### 4.1 取消的开发任务

> 以下任务请从客户端 / SDK 开发计划中**完全取消**——不再属于 A2C-SMCP 范围。

| 任务 | 原计划范围 | 状态 |
|------|----------|------|
| `client:get_dpe` 事件实现 | Agent SDK + Computer SDK | ❌ **取消**（事件已删除）|
| DPE Resolver Hook 注册 API | Computer SDK | ❌ **取消** |
| `dpe://` URI 解析器 | Agent SDK + Computer SDK | ❌ **取消**（URI scheme 迁出 A2C）|
| 双 mimetype 解析（inline / uri）| Computer SDK | ❌ **取消** |
| 4011 / 4012 / 4013 错误处理 | Agent SDK | ❌ **取消** |
| 4013 `category` 4 枚举值处理 | Agent SDK | ❌ **取消** |
| Finder 错误码 4201-4204 | 全部 SDK | ❌ **取消** |
| host 唯一性硬约束（注册阻塞）| Computer SDK | ⚠️ **降级** 为 lint-style WARN |
| DPE Resource `_meta.expires_at` / `_meta.etag` | 全部 SDK | ❌ **取消** |
| Resolver 输入输出 `A2CResource` 同形载体 | Computer SDK | ⚠️ **类型保留**但不再用于 DPE |

### 4.2 保留的开发任务（v0.2 非 DPE 改动）

> 这些**继续按计划开发**：

| 任务 | 范围 |
|------|------|
| `window://` URI 纯标识符化 | 全部 SDK |
| Resource annotations / _meta 元数据下沉 | MCP Server helpers + Agent / Computer SDK |
| priority 类型从 `int [0,100]` 改为 `float [0,1]` | 全部 SDK |
| Socket.IO connect 阶段 `?a2c_version=` 握手 | Agent / Computer SDK + Server |
| 4008 HTTP body code 处理 | Agent / Computer SDK |
| 4006 / 4007（MCP 上游授权）| Computer SDK + Agent SDK |
| 4014 / 4015（MCP Server 路由）| Computer SDK + Agent SDK |
| `client:get_resources`（透明转发 MCP resources/list） | Agent / Computer SDK |
| 4001 描述收紧 | 全部 SDK |
| host 跨 Server SHOULD 唯一（WARN 不阻塞）| Computer SDK |

### 4.3 新增的对接任务（如团队同时支持 DPE）

> 如果团队仍需支持 DPE 文档分发能力，请**单独**对接 dpe-protocol，**不**在 A2C-SMCP SDK 内做。

| 任务 | 对接位置 |
|------|---------|
| OCI Distribution 客户端集成（推荐 ORAS）| 业务层独立模块 |
| DPE 哈希计算（SHA-256 hex[:32] + length-prefix） | 跨语言 dpe-core 库 |
| Document / DocPage / DocElement schema 解析 | 跨语言 dpe-core 库 |
| `dpe://` URI 解析（new spec） | 跨语言 dpe-core 库 |

详见 [dpe-protocol/README.md](https://github.com/A2C-SMCP/dpe-protocol#readme) 路线图。

---

## 5. 升级路径

### 5.1 已经完成 v0.2 草案 DPE 实现的 SDK

需要回退（rollback）DPE 相关代码：

```bash
# 1. 删除 client:get_dpe 事件类型与处理函数
# 2. 删除 4011/4012/4013/4201-4204 错误码
# 3. 删除 GetDPEReq / GetDPERet / Resolver* 类型
# 4. 删除 dpe:// URI 解析器
# 5. 解除 host 唯一性硬约束
# 6. 测试套件中的 DPE 用例标记为 obsolete 或迁移到 dpe-protocol SDK 测试
```

### 5.2 尚未实现 DPE 的 SDK（greenfield）

直接按本变更报告的 §4.1 / §4.2 区分：取消 §4.1 任务、按计划做 §4.2。无需实现任何 DPE 相关代码。

### 5.3 业务层（Computer 部署方）

之前 v0.2 草案要求业务方实现 DPE Resolver Hook——**该需求取消**。如业务确实需要分发结构化文档：

- 直接采纳 dpe-protocol（基于 OCI Distribution，业务方自部署 zot / Harbor / Docker Distribution，存储后端 MinIO / S3 / GCS 任选）
- 与 A2C-SMCP 完全解耦——dpe-protocol 客户端独立实例化、独立鉴权、独立网络通道

---

## 6. FAQ

### Q1：A2C-SMCP 是否还能用来分发任何文件？

A2C-SMCP 控制面 Socket.IO 通道**仍然可用**于小尺寸数据（`window://` 资源、`client:get_resources` 元数据列表、工具调用结果）。**不再**承载结构化文档分发。

### Q2：现有部署的 v0.1 MCP Server（暴露 `dpe://` 资源）怎么办？

升级到 v0.2 后，A2C-SMCP 协议层**不再处理** `dpe://` URI——MCP Server 即使继续暴露这些 Resource，Agent 通过 `client:get_resources` 仍能列出（透明转发），但调用 `client:get_dpe`（已删除）会返回 unknown event 错误。建议：

- **推荐**：MCP Server 改为暴露纯文本 / Window URI Resource；DPE 内容分发改走 dpe-protocol 独立通道
- **过渡**：MCP Server 暂时保留 `dpe://` Resource 作为元信息列表，但 Agent 不调用 `client:get_dpe`

### Q3：是否还要保留 `_meta.expires_at` / `_meta.etag` 字段定义？

**不保留**——这俩字段是 v0.2 草案 DPE Resolver 输出 hint，与 A2C-SMCP 控制面无关。Resource 通用 `_meta` 仍是协议扩展点，但不预定义 DPE 相关字段。

### Q4：dpe-protocol 仓库的开发节奏？

dpe-protocol 处于 v0.1 草案阶段（README + storage-layout + merkle-hash-spec + data-model 四份核心文档）。Python SDK / 测试向量集 / docker-compose 示例 / OCI mediaType 注册等正在路线图上。详见 [dpe-protocol README §路线图](https://github.com/A2C-SMCP/dpe-protocol#路线图)。

---

## 7. 行动清单（给团队 leader）

- [ ] 通知 python-sdk 团队按 §4.1 取消 DPE 任务
- [ ] 通知 rust-sdk 团队同上
- [ ] 通知所有已对接 v0.2 草案的业务方：DPE Resolver Hook 实现工作取消
- [ ] 评估是否单独立项对接 dpe-protocol（取决于业务是否需要结构化文档分发）
- [ ] 关闭 / 转移已开 issue：DPE 相关 issue 转到 dpe-protocol 仓库；非 DPE issue 留在 a2c-smcp-protocol

---

## 8. 关联资源

- A2C-SMCP 协议规范（更新后）：[github.com/A2C-SMCP/a2c-smcp-protocol](https://github.com/A2C-SMCP/a2c-smcp-protocol)
- DPE 协议规范（独立仓库）：[github.com/A2C-SMCP/dpe-protocol](https://github.com/A2C-SMCP/dpe-protocol)
- v0.2 升级指南（更新后）：[`docs/migrations/v0.2-uri-metadata-refactor.md`](docs/migrations/v0.2-uri-metadata-refactor.md)
