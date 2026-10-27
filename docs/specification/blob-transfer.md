# 通用二进制传输

## 概述

通用二进制传输是 A2C-SMCP 的**跨通道双向字节搬运层**：

- **下行（Computer → Agent）**：任何需要把较大 / 二进制内容从 Computer 送达 Agent 的通道，都不把字节塞进自己的响应，而是在响应里铸造一个 **`blob_handle`**，由 Agent SDK 经统一的 `client:get_blob` 事件分块拉取。
- **上行（Agent → Computer）**：Agent 需要把（二进制 / 大文本）内容**落盘到 Computer 的既定安全位置**（landing root）供 Computer 侧工具二次分析时，经统一的 `client:put_blob` 事件分块上传；Computer 落盘后返回**绝对 `landing_path`**，Agent 把它作为参数直接嵌入后续 `client:tool_call`（Bash / MCP 工具）使用。

```
┌── 生产者通道（如 SKILL）────────────┐      ┌── Agent 落盘（写入通道）─────────┐
│ client:get_skill                    │      │ client:put_blob                    │
│   文本且可内联 → body               │      │   分块上行 → landing root 落盘     │
│   二进制 / 过大 → blob_handle ──────┼──┐   │   返回绝对 landing_path ──────────┼──┐
└─────────────────────────────────────┘  │   └───────────────────────────────────┘  │
                                          ▼                                           │
                            ┌── 通用传输 ───────────────┐                             │
                            │ client:get_blob（下行）    │                             │
                            │   (blob_handle, offset)   │                             │
                            │   → 分块 base64 + sha256  │                             │
                            │ client:put_blob（上行）    │                             │
                            │   (upload_id, offset)     │                             │
                            │   → 分块 base64 + sha256  │                             │
                            └───────────────────────────┘                             │
                                                                                       ▼
                                            ┌──────────────────────────────────────┐
                                            │ client:tool_call（Bash / MCP）        │
                                            │   参数直接携带 landing_path           │
                                            └──────────────────────────────────────┘
```

### 为什么独立成通道

| 目标 | 说明 |
|---|---|
| **生产者通道保持精简** | SKILL 等通道只表达自身语义；字节泵机制（分块 / 背压 / 完整性 / 上限）定义一次 |
| **复用** | 任何 Agent↔Computer 字节场景（SKILL 资源、未来大 tool_call 结果 / desktop 截图 / artifact 通道、Agent 落盘产物）共用同一契约 |
| **演进解耦** | 传输层加压缩 / etag 等优化，生产者通道零改动 |

### 设计原则

1. **句柄即不透明能力引用**（下行）——`blob_handle` 由 Computer 铸造，Agent 视为不透明 token
2. **无状态**（下行）——Computer 每次调用即时解析句柄，**无 session、无 TTL**；幂等、可续传、可并行
3. **传输 ≠ 鉴权**——`client:get_blob` 是搬运层；鉴权属于**铸造句柄的生产者通道**，解析时重新施加
4. **pull 即背压 / ack-paced 即节流**——下行 Agent 决定何时取下一块；上行 Agent 逐块等 ack，Computer 永不超速 / 不被打爆
5. **沙箱由写入原语强制**（上行）——Agent 拿不到「写任意路径」的能力，只能把字节写进 Computer 决断的落点；返回的 `landing_path` 使 Agent **感知不到沙箱的存在**（无需任何解析 API，直接当普通路径用）

---

## 1. BlobHandle 契约

```
BlobHandle: TypeAlias = str
```

| 约束 | 强度 | 说明 |
|---|---|---|
| 不透明 | **MUST** | Agent **MUST NOT** 解析 / 拼接 / 伪造 / 跨 Computer 复用句柄 |
| Computer 铸造 | **MUST** | 仅由生产者通道在其成功且已授权的响应中产生 |
| 无状态可重解析 | **MUST** | Computer 每次调用从句柄确定性解析回源；**禁止**服务端会话 / 游标 / TTL |
| 鉴权随源 | **MUST** | 解析时**重新施加铸造通道的授权与边界**（SKILL → [§9 沙箱](skill.md#9-安全模型)）；句柄解码出的路径**绝不**被直接信任 |
| 非任意文件读 | **MUST** | `client:get_blob` **不是**"读 Computer 任意文件"的原语；只服务**生产者通道已授权**的源。按路径读取的生产者 [`client:resolve_path`](#生产者三按路径读取) 同样受此约束：其授权边界 = Computer 用户配置的 `readRoots`（默认空 = 不可读）|
| 仅下行 | — | 上行 `client:put_blob` **不铸造句柄**，返回绝对 `landing_path`（[§3](#3-事件-clientput_blob上行写入)）；句柄契约（不透明 / 可重解析 / 重施鉴权）只适用于下行 |

!!! danger "句柄不是绕过鉴权的后门"

    若生产者通道（如 SKILL）在铸造句柄前已拒绝（`.skillenv` / 越权 / 超上限 → 不铸造），则该资源**根本没有句柄**。`client:get_blob` 解析任何句柄时仍 **MUST** 重跑源通道的边界校验（防御纵深）：源已变为 orphan / 被删 / 现在越权 → [`4018`](error-handling.md#blob-not-accessible4018)。

---

## 2. 事件 `client:get_blob`

通用：Agent → Server → Computer，Server 按 `computer` 路由（与其它 `client:*` 同）。

**请求数据 (GetBlobReq)**:
```python
{
    "agent": str,
    "req_id": str,
    "computer": str,
    "blob_handle": str,      # 来自某通道响应的不透明句柄
    "chunk_offset": int,     # 可选：资源字节绝对偏移；缺省 0（无状态幂等）
    "max_chunk_bytes": int   # 可选：客户建议单块上限；Computer clamp
}
```

**响应数据 (GetBlobRet)**:
```python
{
    "blob_handle": str,  # 回显
    "mime_type": str,    # 资源 MIME
    "total_size": int,   # 资源总字节数（首块即知；一次读取内恒定）
    "sha256": str,       # 全量资源 sha256 十六进制（跨块恒定）
    "chunk_offset": int, # 本块起始字节偏移
    "eof": bool,         # ⟺ chunk_offset + 本块字节数 == total_size
    "blob": str,         # base64，本块字节
    "req_id": str
}
```

**Computer 处理流程**：

1. 解析 `blob_handle` 回源（不透明 → 源描述符）；无法识别 / 格式非法 → [`4018`](error-handling.md#blob-not-accessible4018) `invalid_handle`
2. **重施铸造通道鉴权**：SKILL 源 → 重跑 [§9 沙箱](skill.md#9-安全模型)（Registry 仍含、未孤儿、`.skillenv` 等仍 forbidden）；path 源 → 按**当前** `readRoots` 重跑 [resolve 第 3–8 步](#computer-处理流程)（围栏 / 固定拒绝集 / 权限）。失败 → `4018` `forbidden`
3. 源已不可达（SKILL 卸载 / 文件删除 / path 源被删除或已非普通文件 / 内容已变得无法服务）→ `4018` `gone`
4. `chunk_offset < 0` 或 `> total_size` → `4018` `range`
5. 从 `chunk_offset` 起取 `min(max_chunk_bytes, Computer cap)` 字节；`max_chunk_bytes` 缺省时 Computer 自定，**恒保证序列化后 ≤ Server `maxHttpBufferSize`**（计入 base64 +33% 与 envelope）
6. 回填 `total_size` / `sha256`（全量资源）/ `chunk_offset` / `eof`；本块字节 base64 → `blob`

---

## 3. 事件 `client:put_blob`（上行写入）

通用：Agent → Server → Computer，Server 按 `computer` 路由（与其它 `client:*` 同）。分块上行是 `client:get_blob` 的**方向镜像**：`chunk_offset` / `eof` 由 **Agent 驱动推进**，`sha256` / `total_size` 由 **Agent 声明、Computer 校验**（与下行「Computer 声明、Agent 校验」镜像）。

**请求数据 (PutBlobReq)**:

```python
{
    "agent": str,
    "req_id": str,
    "computer": str,
    "upload_id": str,     # 可选：缺省即首块（offset 0），Computer 分配并回传
    "chunk_offset": int,  # 本块起始字节偏移；MUST == Computer 已收字节（in-order）
    "eof": bool,          # 末块标志
    "total_size": int,    # 仅首块：声明总字节（MUST ≥ 1）
    "sha256": str,        # 仅首块：声明全量 sha256（十六进制）
    "name_hint": str,     # 仅首块可选：建议文件名；Computer 消毒后采用或自定
    "blob": str           # base64，本块字节
}
```

**响应数据 (PutBlobRet)**:

```python
{
    "upload_id": str,      # 首块 ack 回传；后续块回显
    "chunk_offset": int,   # 回显本块起始字节偏移
    "landing_path": str,   # 仅末块 ack：landing root 内绝对路径（安全名）
    "total_size": int,     # 仅末块 ack：实际落盘字节（== 声明值才成功）
    "sha256": str,         # 仅末块 ack：Computer 重算全量 sha256（== 声明值）
    "req_id": str
}
```

**Computer 处理流程**：

1. **首块**（无 `upload_id`、`chunk_offset=0`）：校验声明（字段齐备、`total_size ≥ 1`）→ 非法 → [`4019`](error-handling.md#blob-write-failed4019) `invalid_declaration`；`total_size` 超 Computer 可配上限 → `4019` `too_large`（**零字节落盘**）；并发上传会话已达上限 → `4019` `busy`；通过 → 创建会话（`.part` 临时文件 + 增量 hasher + 已收字节计数），分配 `upload_id` 回传
2. **后续块**：`upload_id` 无法识别 / 已过期 → `4019` `invalid_upload`；`chunk_offset != 已收字节` → `4019` `range`（in-order 强制，无稀疏缓冲）。`total_size` / `sha256` / `name_hint` 仅首块携带，后续块 MUST NOT 携带（违反 → `4019` `invalid_declaration`）
3. 每块 base64 解码 → 追加 `.part` → 增量 hasher 更新。单块序列化后 MUST ≤ Server `maxHttpBufferSize`（计入 base64 +33% 与 envelope；Agent 责任，参考预算 256 KiB 默认块）
4. **末块**（`eof=true`，且 `chunk_offset + 本块字节数 == total_size`，否则 `4019` `range`）：关闭 `.part`，重算全量 sha256 与声明比对 → 不符 → `4019` `integrity`（**丢弃，不返回 path**）；通过 → 原子 rename 进 landing root（安全名 = `upload_id` 派生 + 消毒后的 `name_hint`），返回 `landing_path` / `total_size` / `sha256`
5. 落盘 IO 失败（磁盘满 / 权限 / landing root 不可写）→ `4019` `io_error` / `forbidden`（见 [§7](#7-写入侧契约landing-沙箱)）

### 上传会话生命周期（有界 MUST）

`upload_id` 会话是 Computer 侧**受限状态**（`.part` + 已收字节 + hasher）。与下行句柄的「无状态可重解析」不同，上传**天生有会话**——协议要求它**有界**：

| 约束 | 强度 | 说明 |
|---|---|---|
| 闲置超时 | **MUST** | 会话闲置超时后作废（阈值 SDK 自治、可配）；此后该 `upload_id` → `4019` `invalid_upload` |
| 并发上限 | **MUST** | 同时在途上传会话数有上限（阈值 SDK 自治、可配）；打满 → `4019` `busy`，Agent SHOULD 退避后重试 |
| 孤儿回收 | **MUST** | 废弃 / 崩溃遗留的 `.part` 由 landing GC 回收（严格限于 landing root，见 [§7](#7-写入侧契约landing-沙箱)） |
| 无跨尝试断点 | **MUST** | 任何失败后的重试 = **新 `upload_id` 从 offset 0 重传**；无断点续传、无去重状态（与下行「跨块变化从 0 重读」对称） |

### 能力门控（版本握手，无协商字段）

`client:put_blob` 无独立能力协商机制。协议 v0.x 兼容性判定为 **MINOR 严格匹配**（[versioning.md](versioning.md#兼容性判定规则)）且同房间传递（Agent.minor == Server.minor == Computer.minor）：**Agent 以「自身 minor ≥ 0.4 且已连接」为能力门控**——连上即保证房内 Computer 为同 minor；PATCH 只出 bugfix、功能只随 MINOR，故 0.4.x Computer 必有 put_blob（本事件为 0.4.0 起 Computer **MUST** 实现）。超时探测仅作**防御性兜底**（`-dev` 周期内双 SDK 实现进度不同步 / 不合规实现的边界场景）：首块超时视为不支持，字节留上下文不落盘；**不是**正式回退路径。

### 时序

```mermaid
sequenceDiagram
    participant A as Agent
    participant S as Server
    participant C as Computer

    A->>S: client:put_blob（首块：total_size, sha256, name_hint?）
    S->>C: 转发
    C->>C: 校验声明（too_large / busy → 4019 零落盘）→ 创建会话
    C->>S: PutBlobRet { upload_id }
    S->>A: PutBlobRet { upload_id }
    loop 中间块（ack-paced 即节流）
        A->>S: client:put_blob（upload_id, chunk_offset, blob）
        S->>C: 转发
        C->>C: in-order 校验 → 追加 .part + hasher.update
        C->>S: PutBlobRet { upload_id, chunk_offset }
        S->>A: PutBlobRet
    end
    A->>S: client:put_blob（末块 eof=true）
    S->>C: 转发
    C->>C: sha256 重算比对 → 原子 rename 进 landing root
    C->>S: PutBlobRet { landing_path, total_size, sha256 }
    S->>A: PutBlobRet
    Note over A: landing_path 直接嵌入后续 tool_call 参数（Bash / MCP）
```

---

## 4. 分块 / 背压 / 完整性 / 上限

| 关注点 | 方向 | 协议落位 |
|---|---|---|
| **背压** | 下行 | pull 模型内生——Agent 控制取下一块的节奏，Computer 不推送，无需字段 |
| **背压** | 上行 | ack-paced 内生——Agent 逐块等 ack 再发下一块（顺序发送），Computer 不被压垮，无需字段 |
| **续传 / 重试 / 并行** | 下行 | `chunk_offset` 是**资源解码后字节的绝对偏移**，无服务端状态 → 天然幂等、可并行不同 offset |
| **续传 / 重试** | 上行 | **无跨尝试断点**：任何失败 → 新 `upload_id` 从 offset 0 重传；尝试内 in-order 强制（offset == 已收字节），无并行、无去重状态 |
| **完整性** | 下行 | `sha256` = 全量资源 sha256（跨块恒定）；Agent `eof` 后 **SHOULD** 校验重组内容，不符即损坏并重读 |
| **完整性** | 上行 | 镜像：`sha256` 由 **Agent 首块声明**，Computer 接收期增量计算、末块重算比对，不符 → `4019 integrity`（丢弃不落盘）；末块 ack 回显重算值，Agent **SHOULD** 比对声明 |
| **读取中变更** | 下行 | `sha256` / `total_size` 一次逻辑读取内 **MUST** 稳定；Agent 跨块发现变化 ⇒ 源被改写，**MUST** 从 offset 0 重读，不拼接错配字节；Computer **SHOULD** 尽力一致快照 |
| **读取中变更** | 上行 | 不适用——声明即契约：首块声明后不可变；后续块携带声明字段 MUST NOT，违反 → `4019 invalid_declaration` |
| **绝对上限（DoS）** | 下行 | 由**铸造通道在铸造时**决断（SKILL → `total_size` 超 SDK 可配上限即 [`4017 too_large`](error-handling.md#skill-resource-not-accessible4017)，不铸造句柄）。`client:get_blob` 只服务已通过上限的句柄。按路径读取（`client:resolve_path`）**不设**绝对上限：文件由 Computer 用户显式授权，`total_size` 先于任何字节告知 Agent，拉取多少由 Agent 依 pull 模型自决 |
| **绝对上限（DoS）** | 上行 | 由 **Computer 在首块决断**：声明 `total_size` 超可配上限 → `4019 too_large`（**零字节落盘**）；叠加会话有界（闲置超时 + 并发上限，见 [§3](#3-事件-clientput_blob上行写入)） |

!!! note "「资源字节」基准"

    `total_size` / `chunk_offset` / `sha256` 一律基于 **Agent 最终消费的资源字节**——由生产者通道定义（SKILL.md → frontmatter 剥离后 body；其它文件 → 原始字节；占位符不展开）。空资源 = `total_size=0`，单次响应 `eof=true`、`blob=""`。

!!! note "预留演进缝隙（勿破坏）"

    `GetBlobReq` / `GetBlobRet` / `PutBlobReq` / `PutBlobRet` 为开放 TypedDict，未来可**非破坏**追加 `content_encoding`（gzip 等，缺省 identity；届时 `blob` = base64 of 已 content-encoded 字节）、`etag`；`4018.details.reason` 与 `4019.details.reason` 为开放枚举。offset / total_size / sha256 基于**解码后**资源字节，加压缩不致歧义。

### 时序（以 SKILL 二进制资源为例）

```mermaid
sequenceDiagram
    participant A as Agent
    participant S as Server
    participant C as Computer

    A->>S: client:get_skill(name, rel_path)
    S->>C: 转发
    C->>C: 解析 rel_path → §9 沙箱 + too_large 校验 → 铸造 blob_handle
    C->>S: GetSkillRet { mime_type, total_size, sha256, blob_handle }
    S->>A: GetSkillRet
    loop 直至 eof（pull 即背压）
        A->>S: client:get_blob(blob_handle, chunk_offset)
        S->>C: 转发
        C->>C: 解析句柄 → 重施 §9 → 切片
        C->>S: GetBlobRet { blob, chunk_offset, eof, sha256 }
        S->>A: GetBlobRet
    end
    Note over A: 重组后校验 sha256
```

---

## 5. 错误模型

| 码 | 归属 | 触发 |
|---|---|---|
| [`4017`](error-handling.md#skill-resource-not-accessible4017) | **生产者 SKILL（下行铸造期）** | 铸造前解析失败：`rel_path` 穿越 / `.skillenv` forbidden / 不存在 / `too_large`。**不**铸造句柄 |
| MCP `CallToolResult.isError` | **生产者 tool_call（下行铸造期）** | 工具自身失败沿用 MCP 错误惯例（**不**引入 A2C 事件级码——既有协议不变量）|
| [`4020`](error-handling.md#path-not-accessible4020) | **生产者 path（下行铸造期）** | `client:resolve_path` 解析失败：路径非法 / 越出 `readRoots` / 不存在 / 非普通文件（`details.reason` ∈ `invalid_path` / `forbidden` / `not_found` / `not_a_file`）。**不**铸造句柄 |
| [`4018`](error-handling.md#blob-not-accessible4018) | **本通道（下行拉取期）** | 句柄无效 / 重施鉴权失败 / 源消失 / 范围越界（`details.reason` ∈ `invalid_handle` / `forbidden` / `gone` / `range`）|
| [`4019`](error-handling.md#blob-write-failed4019) | **本通道（上行写入期）** | 会话无效 / 声明非法 / 顺序错乱 / 超上限 / 会话繁忙 / 沙箱不可写 / 完整性不符 / IO 失败（`details.reason` ∈ `invalid_upload` / `invalid_declaration` / `range` / `too_large` / `busy` / `forbidden` / `integrity` / `io_error`）|

边界清晰：下行**铸造期**失败按各生产者自身错误惯例（SKILL→`4017`；tool_call→MCP `isError`；path→`4020`）；下行**拉取期**的句柄/源/范围一律 `4018`；上行**写入期**的一切失败一律 `4019`。**4018 与 4019 方向相反、互不重叠；4017 与 MCP `isError` 不用于上行。**

---

## 6. 下行生产者通道接入契约

任何通道要产出 `blob_handle`，**MUST**：

1. 在**自身响应**中铸造不透明、无状态、可重解析的句柄（含足以确定性回源的信息）
2. 在**铸造时**完成本通道的鉴权与资源上限校验；不通过则**不铸造句柄**、按本通道错误码返回（SKILL → `4017`）
3. 文档化句柄的**有效期语义**：本协议不设 TTL；句柄"有效"等价于"源仍被本通道授权且可解析"。源变更由 `sha256` / `total_size` 检测，源消失由 [`4018 gone`](error-handling.md#blob-not-accessible4018) 表达
4. 句柄**绝不**编码可被 Agent 利用来越权的明文路径；即便编码，Computer 解析时 **MUST** 重跑本通道边界校验，不信任句柄内容

### 一致性铁律：所有生产者拉取契约相同，仅载体位置随结构而异

`blob_handle` 的**语义、拉取（`client:get_blob`）、`sha256`/`total_size` 前置元数据、4018 错误模型、Agent 重组/校验流程**对所有生产者**完全相同**。**唯一**允许的差异是句柄的**承载位置**——且该差异**仅**由"响应结构是否可变"决定，非设计自由度：

| 生产者 | 响应结构 | 句柄载体 | 对等元数据 | 铸造期失败惯例 |
|---|---|---|---|---|
| `client:get_skill` | `GetSkillRet`（A2C 自有，可改） | **顶层** `blob_handle` | 顶层 `total_size` / `sha256` / `mime_type` | A2C [`4017`](error-handling.md#skill-resource-not-accessible4017) |
| `client:tool_call` | MCP `CallToolResult`（**标准不可变**） | content item `_meta.`**`a2c_blob_handle`** | item `_meta.a2c_total_size` / `_meta.a2c_sha256` + item 既有 `mimeType` | MCP `CallToolResult.isError` |
| `client:resolve_path` | `ResolvePathRet`（A2C 自有，可改） | **顶层** `blob_handle` | 顶层 `total_size` / `sha256` / `mime_type`（另含 `canonical_path` / `mtime`）| A2C [`4020`](error-handling.md#path-not-accessible4020) |

> CallToolResult 走 `_meta` 旁路与 `SMCPTool.meta` 的 `a2c_tool_meta` / `MCP_TOOL_ANNOTATION` 命名空间旁路**同构**——这是 A2C 在不可变 MCP 结构上扩展的既定手法，不是新约定。

Agent SDK 因此只有"**去哪找句柄**"一处分支（顶层字段 vs 遍历 content item `_meta`）；句柄拿到后的拉取、`sha256` 校验、`4018` 处理是**同一套代码、同一套语义**。

阈值判定同源：文本 ≤ 内联预算 → 内联；二进制 / 文本超预算 → 句柄。tool_call **逐个**二进制 content item 独立按此预算判定。

### 生产者一：SKILL

`client:get_skill` 对二进制 / 过大文本资源铸造顶层 `blob_handle`；铸造前在解析阶段完成 [§9 沙箱](skill.md#9-安全模型) 与 `too_large`。详见 [SKILL 通道 §7](skill.md#7-事件)。

### 生产者二：tool_call

`client:tool_call` 返回原生 `CallToolResult`；超内联预算的二进制 content item 清空内联 `data`/`blob`、在其 `_meta` 写 `a2c_blob_handle`（+`a2c_total_size`/`a2c_sha256`）。CallToolResult 仍是合法 MCP 结构；工具自身失败仍走 MCP `isError`。详见 [事件定义 §client:tool_call](events.md#clienttool_call)。

### 生产者三：按路径读取

**`client:resolve_path`（v0.5.0 起，protocol#65）**：Agent 给出 Computer 本地文件路径，Computer 规范化 → 校验 `readRoots` → stat，返回该文件的规范路径与元数据，并**现铸**一个 `blob_handle`；字节仍经 `client:get_blob` 拉取（分块 / `sha256` / `4018` 全部复用）。本事件**不**新增 handle kind，也**不**让 Agent 构造句柄——句柄仍由 Computer 在已授权的生产者响应中铸造（[§1](#1-blobhandle-契约)）。

**请求数据 (ResolvePathReq)**:
```python
{
    "agent": str,
    "req_id": str,
    "computer": str,
    "path": str          # Computer 本地绝对路径：原生形态（POSIX "/..."；Windows "C:\..." / "C:/..."）或 canonical_path 形态（"/C:/..."）
}
```

**响应数据 (ResolvePathRet)**:
```python
{
    "canonical_path": str,  # 规范路径（realpath 后，见下文 §canonical_path 规范化）
    "blob_handle": str,     # 现铸的不透明句柄（转 client:get_blob 拉字节）
    "mime_type": str,       # 确定性推断（同 SKILL §6.4 (1)）
    "total_size": int,      # 文件字节数
    "sha256": str,          # 全量 sha256 十六进制
    "mtime": int,           # 最后修改时间：Unix epoch 毫秒（向下取整，仅作提示）
    "req_id": str
}
```

#### Computer 处理流程

顺序 **MUST** 如下（前序失败即返回，不执行后序；**越界判定先于任何存在性探测**，不泄露授权边界外文件的存在性）：

1. `n = normalize_path(path)` 失败 → [`4020`](error-handling.md#path-not-accessible4020) `invalid_path`。**`..` 在此按词法消解**（先于符号链接解析）——后续步骤一律以 `n` 为准，**MUST NOT** 对原始 `path` 做 realpath
2. `readRoots` 为空 → `4020` `forbidden`
3. **词法围栏**：`n` 不落在任一 root 的**配置形态或 realpath 形态**内（见 [§readRoots](#readroots读取授权根config-first)）→ `4020` `forbidden`（**不**访问文件系统）
4. **非严格 realpath**：对 `native(n)` 做 realpath——解析**最长已存在前缀**上的全部符号链接，再原样拼接其余（尚不存在的）分量；Windows realpath 若返回 `\\?\` 前缀形态一并剥离。结果经 `normalize_path` 得 `canonical_path`。`native(n)`：POSIX 为 `n` 本身；Windows 为 `/X:/a/b` → `X:\a\b`
5. **realpath 围栏**：`canonical_path` 不落在任一 root 的 realpath 形态内（如符号链接越界）→ `4020` `forbidden`；realpath 结果无法以 Unicode 字符串表示或无法规范化（如解析到 UNC）→ `4020` `forbidden`。**本步通过之前**，任何文件系统错误（含 realpath / stat 失败）一律 → `4020` `forbidden`，**MUST NOT** 回 `not_found`
6. **固定拒绝集**：`canonical_path` 命中 [§固定拒绝集](#固定拒绝集) → `4020` `forbidden`（不因 `readRoots` 授权而放行）
7. 打开文件（**SHOULD** 不跟随末级符号链接）：`ENOENT` / `ENOTDIR` → `4020` `not_found`；`EACCES` / `EPERM` 等权限类错误 → `4020` `forbidden`
8. 对**已打开的句柄**校验：非普通文件（目录 / 设备 / FIFO / socket 等）→ `4020` `not_a_file`；Computer **SHOULD** 取该句柄的最终路径（如 `/proc/self/fd`、`F_GETPATH`、`GetFinalPathNameByHandle`）重跑第 5–6 步，不符 → `4020` `forbidden`
9. 从**同一打开句柄**取 `total_size` / `mtime` 并计算 `sha256`（**MUST NOT** 关闭后按路径重新打开）；按 [SKILL §6.4 (1)](skill.md#64-mime_type-确定性与文本-mime判据) 的确定性映射推断 `mime_type`；铸造 `blob_handle`（MUST 足以在拉取期确定性回到 `canonical_path`）

**`sha256` 计算口径**（owner 裁决）：协议**不设**文件大小上限，`client:resolve_path` 受常规请求超时约束（超时按常规超时处理，不另设错误码）；`sha256` **MUST** 返回。Computer **MAY** 缓存摘要，键 **MUST** 至少含 `(canonical_path, total_size, mtime)`，**SHOULD** 再含文件身份（inode / file-id）与 ctime（若平台提供）——缓存的强度只等于其键：同尺寸且 mtime 粒度内的改写可能命中旧摘要，键有任何疑义时 **MUST** 重算。为使大文件可读，Computer **SHOULD** 在请求超时后**继续完成**该摘要计算并写入缓存（重试即可命中），并 **SHOULD** 对同一键的并发计算去重。

**拉取期**：`client:get_blob` 解析 path 句柄时 **MUST** 按**当前** `readRoots` 与当前文件系统状态重跑第 3–8 步（防御纵深，覆盖 resolve 之后被换掉的符号链接与撤权），并从本次打开的句柄读取字节：第 3 / 5 / 6 步或权限类失败 → [`4018`](error-handling.md#blob-not-accessible4018) `forbidden`；`ENOENT` / `ENOTDIR` 或已非普通文件 → `4018` `gone`。`get_blob` 的 `sha256` / `total_size` **MUST** 描述本次实际提供的字节所属的文件状态：文件身份 / 尺寸 / mtime 与该句柄已知摘要的键不符时 **MUST** 重算，否则 **SHOULD** 复用（避免每块 O(N)）。与 `ResolvePathRet` 不同 ⇒ 文件在 resolve 之后被改写，Agent **SHOULD** 重新 `client:resolve_path`；**同一文件**重组校验连续失败时 Agent **SHOULD** 有界重试（如 1 次）后如实报错，**MUST NOT** 无界循环。

#### 固定拒绝集

`readRoots` 是**用户授权**，但下列文件即便落在授权根内也 **MUST** 拒绝（`4020` `forbidden`；拉取期 `4018` `forbidden`），以保住[零凭证传播](security.md#零凭证传播原则)与 [SKILL `.skillenv` 不变量](skill.md#92-a2c-层补充约束)：

- 末级分量为 `.skillenv` 的文件（任何位置）
- Computer 自身的配置与状态目录内的文件：settings、`computer_id` 存储、input 值缓存、secret / 凭据存储（目录位置 SDK 自治，SDK **MUST** 把自己实际使用的位置纳入本集）
- 上行写入中的未定稿文件（landing root 内的 `.part`）

拒绝集与 `readRoots` 互不替代：`readRoots` 决定「用户愿意给 Robot 读什么」，拒绝集决定「无论用户怎么配都不得经读取通道外流什么」。

#### `readRoots`（读取授权根，config-first）

- **配置项**：Computer settings 键 `readRoots: list[str]`，每项为绝对路径（POSIX `/` 开头或 Windows 盘符）；非绝对项或 `normalize_path` 失败的项按配置诊断丢弃（不生效）。跨受信 scope 的合并沿用 settings 数组默认语义（拼接去重）
- **两种形态**：每个 root 在加载时保留 **配置形态** `normalize_path(配置值)` 与 **realpath 形态** `normalize_path(realpath(配置值))`（如 macOS `/tmp/share` → `/private/tmp/share`；realpath 失败或结果无法规范化（如映射盘解析到 UNC）的 root 只保留配置形态并记配置诊断）。**词法围栏**（第 3 步）对两种形态任一命中即通过；**realpath 围栏**（第 5 步）只认 realpath 形态——安全性只由后者保证，前者仅用于免于访问授权外的文件系统
- **默认空 = 不可读**（fail-closed）：未配置时 `client:resolve_path` 一律 `4020 forbidden`。Robot 能读用户机器上的哪些文件，**由 Computer 端用户决定**
- **scope 门控（协议 MUST）**：与 [`landingRoot`](#landing-root-配置config-first) 对称，仅受信 scope（`user` / `local` / `flag` / `policy` / `embed`）可设；**`project` scope 提供该键 MUST 被 Computer 拒绝**（整字段不生效，属本地配置校验，不产生线上错误码）——clone 的仓库不得把读授权扩到任意路径（如 `~/.ssh`）
- **围栏判定**：`p` 落在 root `r` 内 ⟺ `p == r`，或 `p` 以 `r` 为**路径分量前缀**（`r` 以 `/` 结尾时为 `p.startswith(r)`，否则为 `p.startswith(r + "/")`）。**MUST NOT** 用裸字符串前缀（`/data` 不包含 `/database`）。比较按码点逐一进行（Windows 上除已大写的盘符外**区分大小写**，见下文已知限制）

#### `canonical_path` 规范化

`canonical_path` 的目标是「**同一文件恒得同一路径**」，作为宿主持久引用的路径部分。表示形态由纯函数 `normalize_path(input, platform)` 定义，跨 SDK 由数据向量 [`fixtures/canonical_path_conformance_vectors.json`](fixtures/canonical_path_conformance_vectors.json) 逐字节钉住：

| 规则 | 说明 |
|---|---|
| 通用 | 空串或含 U+0000 → `invalid_path`。**不**做 `~` 展开、**不**做百分号编解码、**不**做 Unicode 归一（NFC / NFD）、**不**改变非盘符部分的大小写 |
| POSIX | MUST 以 `/` 开头；`\` 为普通字符。按 `/` 切段 → 丢弃空段与 `.` → `..` 弹出上一段（已在根时忽略）→ `/` ‖ 段以 `/` 连接。根即 `/`，其余无尾随 `/` |
| Windows | 剥去 `\\?\` 前缀（其后为 `UNC\` → `invalid_path`）→ `\` 一律换 `/` → canonical 形态 `/X:` 剥去开头 `/`（恰为 `X:` 时补 `/`）→ 此时 MUST 以 `X:/` 开头（否则 `invalid_path`：相对路径、裸 `C:` / `C:foo`、无盘符 `/x`、UNC）→ **盘符大写** → 余部同 POSIX 切段 → `/X:/` ‖ 段以 `/` 连接。盘符根即 `/C:/` |
| Windows 分量限制 | 剥去 `\\.\` 设备前缀不支持（`invalid_path`）；盘符之后任一分量含 `<` `>` `:` `"` `|` `?` `*` 或 U+0001–U+001F（含备用数据流 `a.txt:s`），或以 `.` / 空格结尾（`.` 与 `..` 本身除外；Win32 会静默剥除，形态不唯一）→ `invalid_path` |
| 管线 | 词法 `n = normalize_path(input)`；产出 `canonical_path = normalize_path(realpath_nonstrict(native(n)))`（见上文处理流程第 1 / 4 步）。Windows realpath 若返回 `\\?\` 前缀形态，同样经本函数剥离 |

`canonical_path` 是原始路径字符串，可直接作为下一次 `client:resolve_path` 的 `path`（往返稳定：文件未变时再次 resolve 得同一 `canonical_path`）。

!!! note "已知限制（v0.5.0）"

    - **大小写不敏感文件系统**（Windows / 默认 macOS）上同一文件的异形大小写写法，协议**不承诺**归一到同一 `canonical_path`（取决于各 OS realpath 是否返回磁盘上的真实大小写），且词法围栏区分大小写——与 root 配置大小写不同的输入可能在第 3 步即被拒。宿主应以 Computer 返回的 `canonical_path` 为准存储，而非用户输入；Windows 8.3 短名同此。
    - **`..` 词法消解**：`..` 先于符号链接解析按词法消解，与 POSIX shell 的物理语义（`cd link/..`）不同——这是有意的跨 SDK 确定性选择。
    - **Windows 保留设备名**（`CON` / `NUL` 等）不在 `normalize_path` 内拦截，由 realpath / 打开阶段按普通失败处理。
    - **Unicode 归一**：不做 NFC / NFD 归一，保留 OS 返回的码点序列。
    - **UNC / 网络共享路径**（`\\server\share`）本版不支持（`invalid_path`）；POSIX 上无法以 UTF-8 表示的文件名不可解析（`invalid_path`）。

!!! info "`computer://` URI 编码属宿主（非规范）"

    协议只产出原始 `canonical_path`。宿主若组装 `computer://<computer_id><canonical_path>`，**应**按 RFC 3986 对每个路径段做百分号编码（保留分隔 `/`；`:` 属 `pchar` 可不编码，故 `/C:/x` 组装为 `computer://<computer_id>/C:/x`），解析时逐段解码后作为 `path` 交给 `client:resolve_path`。

#### 持久引用 = `computer_id` + `canonical_path`

宿主持久化的是 [`computer_id`](room-model.md#computer-身份) 与 `canonical_path`，**不是** `blob_handle`——句柄短时、不可持久化的规则不变（[§1](#1-blobhandle-契约)）。每次读取：确认当前在房 Computer 的 `computer_id` 与引用一致 → `client:resolve_path(canonical_path)` 现铸句柄 → `client:get_blob` 拉字节。宿主只需校验内容是否变化时，可只比对 `ResolvePathRet.sha256` 而不拉字节。

#### 时序

```mermaid
sequenceDiagram
    participant A as Agent
    participant S as Server
    participant C as Computer

    A->>S: client:resolve_path(path)
    S->>C: 转发
    C->>C: normalize → readRoots 词法围栏 → realpath 围栏 → stat / sha256 → 铸造 blob_handle
    C->>S: ResolvePathRet { canonical_path, total_size, sha256, mime_type, mtime, blob_handle }
    S->>A: ResolvePathRet
    loop 直至 eof（pull 即背压）
        A->>S: client:get_blob(blob_handle, chunk_offset)
        S->>C: 转发
        C->>C: 解析句柄 → 重施 readRoots 围栏 → 切片
        C->>S: GetBlobRet { blob, chunk_offset, eof, sha256 }
        S->>A: GetBlobRet
    end
    Note over A: 重组后校验 sha256
```

---

## 7. 写入侧契约（Landing 沙箱）

`client:put_blob` 的落盘目标与引用语义如下。核心不变量：**写入沙箱由写入原语强制**——Agent 拿不到「写任意路径」的能力，因此也**感知不到沙箱的存在**（返回的 `landing_path` 直接当普通路径用，无解析 API、无需知道 landing root 在哪）。

### landing root 配置（config-first）

- landing root 是 **Computer 侧配置项**（settings 键 `landingRoot`，双 SDK 对齐），协议不向 Agent 暴露其位置；未配置 / 不可写 → `4019` `forbidden`（fail-closed，零字节落盘）
- **scope 门控（协议 MUST）**：`landingRoot` 仅受信 scope（`user` / `local` / `flag` / `policy` / `embed`）可设；**`project` scope 提供该键 MUST 被 Computer 拒绝**——project settings 入 git 随仓库分发，clone 的仓库不得把写目标重定向到任意路径（如 `~/.ssh`），否则掏空沙箱不变量（[computer-management §7 不变量 #6](computer-management/protocol.md#7-安全不变量)）

### `landing_path` 语义

- **绝对路径**、Computer 生成安全名（`upload_id` 派生 + 消毒后的 `name_hint`），构造上严格落在 landing root 内
- Agent 把它**原样嵌入**后续 `client:tool_call` 参数（Bash 命令、MCP 工具路径参数）；Computer SHOULD 令 landing root 对本地工具环境可达（Bash cwd / 挂载 / 配置根），使 `landing_path` 可被工具直接解析——具体机制是部署决策
- **披露权衡（有意设计）**：返回绝对路径会暴露 landing root 的位置（含 OS 用户名级别信息）。这不构成凭据边界——拥有本地 Bash 类工具的 Agent 本就能自行发现该位置；路径披露不带来新能力（写任意路径仍被 `put_blob` 原语锁死）。不做句柄 + 参数重写方案：MCP 工具不认识句柄，Computer 侧重写参数脆弱且难覆盖嵌套参数

### 生命周期与 GC

- **scratch 语义**：落盘产物是本次任务的临时工作物；协议不设 TTL，但 Agent **MUST NOT** 依赖跨任务持久化
- **GC**：Computer MAY 按龄 / 按量回收（策略 SDK 自治）；**MUST** 严格限于 landing root 内（canonicalize + realpath 围栏，不越授权边界——[computer-management §7 不变量 #5](computer-management/protocol.md#7-安全不变量)），且覆盖孤儿 `.part` 与已落盘产物

---

## 8. 实现要求

- **Computer MUST 实现** `client:get_blob`（作为接收方），并对每个句柄解析重施铸造通道鉴权
- **Computer MUST 实现** `client:resolve_path`（0.5.0 起，作为接收方）：`normalize_path` 逐字节符合数据向量 / `readRoots` 默认空 fail-closed / 越界判定先于存在性 / 拉取期重施围栏
- **Computer MUST 实现** `client:put_blob`（0.4.0 起，作为接收方）：声明校验 / in-order / `.part` + 增量 sha256 / 原子 rename / 有界会话（闲置超时 + 并发上限 + 孤儿 GC）/ landing root 沙箱 fail-closed
- **Server MUST 路由** `client:get_blob` / `client:put_blob` / `client:resolve_path`（与其它 `client:*` 一致，按 `computer`）
- **Agent SDK SHOULD 封装** 句柄拉取循环（`while not eof: get_blob(handle, offset)`），并在 `eof` 后校验 `sha256`——可与生产者通道工具封装在同一抽象后，对上层透明
- **Agent SDK SHOULD 封装** 上行落盘循环（首块声明 → ack-paced 逐块发送 → 末块取 `landing_path`），能力门控 = 自身 minor ≥ 0.4（版本握手传递性，见 [§3](#3-事件-clientput_blob上行写入)）

> 协议规范仅提供 Python reference impl；其它 SDK 的封装由各自决定——A2C-SMCP 协议文档不堆砌多语言示例。

---

## 9. 参考

- 数据结构：[`GetBlobReq` / `GetBlobRet` / `BlobHandle` / `PutBlobReq` / `PutBlobRet` / `ResolvePathReq` / `ResolvePathRet`](data-structures.md#通用二进制传输结构)
- 错误码：[`4018 Blob Not Accessible`](error-handling.md#blob-not-accessible4018)、[`4019 Blob Write Failed`](error-handling.md#blob-write-failed4019)、[`4020 Path Not Accessible`](error-handling.md#path-not-accessible4020)
- 一致性向量：[`fixtures/canonical_path_conformance_vectors.json`](fixtures/canonical_path_conformance_vectors.json)
- 首个下行生产者：[SKILL 通道](skill.md)
- 安全边界：[computer-management §7 安全不变量](computer-management/protocol.md#7-安全不变量)、[安全性考虑 §写入通道安全](security.md#写入通道安全landing-沙箱)
