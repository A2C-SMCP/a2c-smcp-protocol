# DPE 文档协议

## 概述

**DPE（Document-Page-Element）** 是 A2C-SMCP 协议中的**文档抽象**——把各种文件格式（PDF / Excel / PPT / HTML / 邮件 / 代码仓库 / ...）统一为"文档-页面-元素"三层结构，通过 MCP Server 暴露 `dpe://` Resource 标准化文件访问语义。

DPE 是**底层抽象，不是文件管理器**——类比 Linux：DPE 对应 POSIX 文件抽象（`open` / `read` / inode 等），不附带文件浏览器。**文档发现、检索、聚合视图**等"管理类"能力**不在 v0.2 协议范围**——未来作为内置 MCP Server（"Finder"）独立提供，让协议本身保持纯粹。

```
┌─────────────────────────────────────────────────────────────────┐
│                          Computer                                │
│                                                                  │
│   ┌──────────┐   ┌──────────┐                                   │
│   │MCP Srv A │   │MCP Srv B │   ← 各自暴露 dpe:// Resource       │
│   │dpe://a   │   │dpe://b   │                                    │
│   │  /report │   │  /slides │                                    │
│   └────┬─────┘   └────┬─────┘                                    │
│        │              │                                           │
│        ▼              ▼                                           │
│   ┌─────────────────────────┐                                    │
│   │   DPE Resolver Hook     │ ← 业务层注册：把 DPE Resource      │
│   │   (业务实现)             │    转成 Agent 可访问的 URI         │
│   └───────────┬─────────────┘                                    │
│               │                                                   │
└───────────────┼───────────────────────────────────────────────────┘
                │  (返回访问 URI)
                ▼
           ┌─────────┐
           │  Agent   │  → 拿到 URI 后用应用层（HTTP/file/...）自取
           └─────────┘
```

DPE 的核心理念：

- **MCP Server 端**：按 MCP 标准暴露 `dpe://` Resource，无需任何 SMCP 特定改动
- **Computer 端**：业务层注册 **DPE Resolver Hook**，决定把 DPE 内容投递给 Agent 的方式（对象存储 / 本地文件 / 任意 URI scheme）
- **Agent 端**：调用 `client:get_dpe` 拿到访问 URI，用应用层协议（HTTP / file / ...）拉取实际内容；DPE 内容形态由文档应用层决定，A2C 协议不规定

---

## DPE 数据模型

DPE（Document-Page-Element）定义了文档内容的三层结构。

### 三层结构

```
Document（文档）
├── Page 0（页面）
│   ├── Element A（元素）
│   ├── Element B
│   └── Element C
├── Page 1
│   ├── Element D
│   └── Element E
└── Page N
    └── ...
```

| 层级 | 说明 | 标识方式 |
|------|------|---------|
| **Document** | 一个完整文档实例（如一份 Excel 工作簿、一个 PDF 文件） | `doc_ref`（MCP Server 分配的不透明短键） |
| **Page** | 文档内的一个逻辑页面（如 Excel 工作表、PDF 页面、PPT 幻灯片） | 从 0 开始的页码索引 |
| **Element** | 页面内的一个内容单元（如表格、段落、图表、图片） | MCP Server 分配的元素 ID |

### 元素类型（参考）

DPE 模型推荐的 19 种标准元素类型（**协议不强制**，由文档应用层自决；列出供 MCP Server 实现参考）：

| 分类 | 元素类型 |
|------|---------|
| 文本类 | `text` / `heading` / `list` / `code` |
| 表格类 | `table` / `pivot_table` |
| 可视化 | `chart` / `diagram` / `image` |
| 数据类 | `formula` / `link` / `annotation` |
| 布局类 | `header` / `footer` / `separator` |
| 媒体类 | `audio` / `video` |
| 交互类 | `form` / `widget` |

完整设计动机与跨格式映射见附录 [DPE 标准化提案](dpe-standardization-proposal.md)。

---

## dpe:// URI 规范

### URI 格式

```
dpe://{host}/{doc-ref}
```

DPE URI 是**纯文档标识符**，**只到 Document 一层**——Page / Element 是文档内部结构，属于内容形态范畴，由 DPE 内容标准 JSON 表达（见 [DPE 内容标准格式](#dpe-内容标准格式)），不在 URI 层级。

DPE URI **不携带 query 参数也不含 fragment**——所有元数据通过 MCP Resource 的 `_meta` / `annotations` 声明（见 [DPE Resource 元数据](#dpe-resource-元数据)）。

### 组成部分

| 组件 | 必填 | 说明 | 约束 |
|------|------|------|------|
| `scheme` | 是 | 固定 `dpe` | 必须为 `dpe`，否则解析失败 |
| `host` | 是 | MCP Server 资源命名空间根 | 不能为空；**单个 MCP Server 内部的 URI 由 MCP `resources/list` 自身保证唯一**；跨 MCP Server **MUST** 唯一（注册期硬约束，详见 [host 路由策略](#host-路由策略)）；**SHOULD** 使用反向域名风格（详见 [host 命名规范](#host-命名规范)，lint-style 引导，不阻塞注册） |
| `doc-ref` | 是 | 文档引用键 | 可以是单段或**分段路径**（多个 `/` 分隔），整体作为文档的唯一标识符；至少含一段 |

### doc-ref 的分段路径表达

`doc-ref` 支持单段或多段 path 形态——MCP Server 开发者可按业务需要选择风格，给出更直观的文档语义表达：

| 风格 | 示例 | 适用场景 |
|---|---|---|
| 单段不透明键 | `dpe://com.example.docs/rpt-2026` | 数据库主键 / 短哈希 / 业务流水号；紧凑稳定 |
| 分段层级路径 | `dpe://com.example.docs/reports/2026/annual` | 按目录组织的文档树；语义自解释 |
| 分段含扩展名 | `dpe://com.example.code/src/main/java/Foo.java` | 代码仓 / 文件系统映射 |
| 时间分段 | `dpe://com.example.mail/inbox/2026-01-15/email-abc` | 时间序列 / 邮件归档 |

**协议视角**：`doc-ref` 是从 host 之后第一个 `/` 起到 URI 结尾的整段 path 字符串。两个 dpe URI 的 doc-ref 是否等价由业务自决（建议按 URL 解码后字符串相等比较）。

### 校验规则

1. `scheme` 必须为 `dpe`
2. `host` 不能为空。**跨 MCP Server MUST 唯一**——Computer 在 MCP Server 注册阶段检测到 host 与已有 Server 冲突时**注册失败**（硬约束）；不存在运行时 host 路由歧义。host **SHOULD** 使用反向域名风格（详见 [host 命名规范](#host-命名规范)）——这是 lint-style 引导，不符合规范的 host（如单段标识符）协议层 WARN 但不拒绝注册
3. `doc-ref` 必须存在且至少含一段非空内容；`dpe://host` 或 `dpe://host/` 形式（doc-ref 为空）视为无效
4. 每段 path 允许 URL 编码（`a%2Fb` 在单段内解码为 `a/b`，与"段间 `/`"语义区分）
5. DPE URI **不允许**携带 query 参数或 fragment——分层处理（详见 [URI query / fragment 处理分层](#uri-query--fragment-处理分层)）：
    - **Agent SDK 构造层**：MUST 校验失败——构造 dpe URI 时检测到 query / fragment 直接拒绝（URI 生产端严格）
    - **Computer 解析层**：容错丢弃 query / fragment + WARN，不影响协议事件成功（URI 消费端宽松，遵循 Postel's law）

### URI 示例

```
dpe://com.example.docs/rpt-2026                      # 单段不透明键
dpe://com.example.docs/reports/2026/annual           # 三段层级路径
dpe://com.example.code/src/main/java/Foo.java        # 含扩展名的代码路径
dpe://com.example.mail/inbox/2026-01-15/email-abc    # 时间分段
```

### host 路由策略

DPE URI 是**自包含寻址凭据**——Agent 只需调 `client:get_dpe(uri=...)`，由 Computer 通过 URI 中的 `host` 反查目标 MCP Server。**host 在 Computer 范围内 MUST 唯一**——以注册期硬约束保证路由确定性。

#### Computer 端实现要求

| 阶段 | 行为 |
|---|---|
| **MCP Server 注册时** | Computer **MUST** 检测新注册 Server 的 host 是否与已注册 Server 冲突；**冲突时注册失败**（硬约束），返回明确错误（含两个 Server 名称 + 共用 host），由运维 / 业务方解决命名冲突 |
| **`client:get_dpe` 路由时** | Computer 按 URI 中的 host 反查 MCP Server 索引：(a) 唯一匹配 → 路由到该 Server；(b) 无匹配 → 返回 `4014 MCP Server Not Found`。**不存在多匹配场景**（注册期已堵） |
| **`client:get_resources` 路由时** | 不受影响——`get_resources` 通过 `mcp_server` 字段直接定位，无需 host 反查 |

#### 设计取向

- **URI 自包含**：保留"一段 dpe URI 字符串就能精确寻址"的语义——Agent 不需要持有外部元信息（mcp_server）才能调用
- **注册期硬约束**：host 重复是 MCP Server 实现的命名 bug，**MUST 在启动期发现并修复**；Computer 不允许带病运行，避免运行时路由歧义跨重启 / 跨部署不一致
- **运行时无歧义**：注册期硬约束保证了 `client:get_dpe` 路由的确定性——同一 URI 在任意时刻、任意部署上路由结果稳定

### host 命名规范

为减少 host 命名冲突概率，协议**推荐**反向域名风格——这是 lint-style 引导，**不是注册期硬约束**（硬约束是唯一性，已由 [host 路由策略](#host-路由策略) 保证）：

| 规则 | 强度 | 内容 |
|------|------|------|
| **反向域名风格** | SHOULD | host **SHOULD** 形如 `<tld>.<organization>.<service>[.<sub>]*`（如 `com.example.docs`）；不符合规范时协议层 WARN 但不阻塞注册 |
| **含业务标识** | SHOULD | 推荐在 host 末段携带服务/业务标识，避免同组织多 server 冲突（`com.example.docs` / `com.example.code` / `com.example.mail`）|
| **全小写** | SHOULD | 全小写 ASCII 字符，仅含字母、数字、点号；不含连字符 / 下划线 / 大写 |
| **避免歧义形式** | SHOULD NOT | 单段标识符（`docs`）、IP 地址、URL 形式（`http://...`）、含端口——这些形式难以保证全局唯一性，强烈建议避免 |

#### 命名示例

```
✅ 推荐：
   com.example.docs                    # 反向域名 + 业务后缀
   com.example.mcp.docs                # 多段层级（反域名 + 服务名 + 业务）
   org.acme.knowledge                  # 组织级（非营利 / 内部）
   io.github.<user>.<project>          # GitHub 项目风格

⚠️  允许但 WARN（不符合 SHOULD，仅在小规模内网部署可接受）：
   docs                                # 单段标识符，命名空间窄
   DOCS.EXAMPLE.COM                    # 大写
   docs.example.com:8080               # 含端口
   docs_server                         # 含下划线
```

> 协议层只对**唯一性**做硬约束（D1）；**命名风格**仅作 lint-style 提示——不符合 SHOULD 的 host 在注册时记 WARN 但仍允许注册成功，由运维自行决定是否修复。

#### 同 Computer 多 MCP Server 部署

同一 Computer 部署多个 MCP Server 时，统一规划 host 命名空间——通常以组织反域名作前缀，按业务子域分配后缀：

```
com.example.docs        # 文档管理
com.example.code        # 代码仓库
com.example.mail        # 邮件归档
com.example.calendar    # 日程
```

---

### URI query / fragment 处理分层

DPE URI **不允许**携带 query 参数或 fragment（语义在 [校验规则](#校验规则) §5 已规定）。但 URI **生产端**与**消费端**对违规情况的应对采用 **Postel's law**——分层处理：

| 层 | 角色 | 行为 |
|----|------|------|
| **Agent SDK 构造层** | URI 生产端 | **MUST 校验失败**：构造 dpe URI 时若入参包含 query / fragment，直接抛出异常，不允许产生违规 URI 进入网络 |
| **Computer 解析层** | URI 消费端 | **容错丢弃 + WARN**：解析任意来源（业务工具返回 / 历史持久化 / 跨 SDK）的 dpe URI 时若检测到 query / fragment，记 WARN 并丢弃后继续解析；**不让协议事件失败**（健壮性优先）|

#### 行为一致性

- 同一段含 query 的 URI（例：`dpe://host/doc?format=md`）
- Agent SDK 构造时：拒绝构造（异常）
- Computer 解析时：解析为 `dpe://host/doc`（丢 `?format=md`）+ WARN 日志

测试矩阵中此类 URI 的预期结果应标 ✅（解析成功，等同于纯标识符）；标 ❌ 是错误结论。

---

## DPE Resource 元数据

MCP Server 通过 `resources/list` 返回的 `Resource` 对象上的 `_meta` 与 `annotations` 字段声明 DPE 文档元数据。

### MCP 标准字段（`annotations`）

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `annotations.audience` | `["user"]` / `["assistant"]` / `["user","assistant"]` | 推荐 | DPE 文档面向 **User** 数据资产，**SHOULD** 声明 `["user"]` |
| `annotations.lastModified` | ISO 8601 字符串 | 否 | 文档最后修改时间；Agent 与未来的 Finder MCP Server 可据此排序 |

### A2C 扩展字段（`_meta`）

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `_meta.keywords` | `list[str]` | 否 | 关键词列表，用于检索/分类 |
| `_meta.file_type` | `str` | 否 | 文件类型（`xlsx`、`pdf`、`pptx` 等） |
| `_meta.page_count` | `int (≥1)` | 推荐 | 文档**逻辑块数 / 最小可独立寻址的代理单元数**；Agent 据此规划翻页 |

### 校验规则

1. `_meta.page_count` 若存在，**MUST** 为正整数（≥ 1）。单页文档约定 `page_count=1`；`0` 与 missing 视为无效（Agent 无法规划翻页，但仍可走 `get_dpe(dpe://host/doc-ref)` 拿整文档 URI）
2. `_meta.keywords` 若存在，必须为字符串数组
3. `_meta.file_type` 若存在，推荐使用小写（如 `xlsx`、`pdf`）
4. `annotations.lastModified` 若存在，必须为 ISO 8601 格式
5. 缺失值同义：`annotations is None` 与 `annotations.{field} is None` 等价；`_meta is None` 与 `_meta.{field} is None` 等价。Computer 不区分缺失原因（DEBUG 级日志即可）

!!! tip "page_count 边界场景"

    - **多页文档**（PDF / Excel / PPT / Markdown 长文）：`page_count=N`，N 为页/sheet/slide/section 数量
    - **单页 / 不可分页文档**（单页 JSON、短文本）：约定 `page_count=1`
    - **真正不应分页的资源**（流式日志、二进制对象）：**不应使用 `dpe://` scheme**——改用 MCP 的其他 scheme

### Resource 完整声明示例

```python
Resource(
    uri="dpe://com.example.docs/rpt-2026",
    name="2026 年度报告",
    description="2026 年度财务与运营报告",
    mimeType="application/json",
    annotations=Annotations(
        audience=["user"],                            # MCP 标准：DPE 面向 User
        lastModified="2026-01-15T08:30:00Z",
    ),
    _meta={
        "keywords": ["财务", "年报"],
        "file_type": "xlsx",
        "page_count": 12,
    },
)
```

> **注**：`_meta.file_uri` 字段已自 v0.2 起删除。物理存储位置由 MCP Server 在 `resources/read` 响应中通过 [`application/vnd.a2c.dpe-uri+json` mimetype](#dpe-文档读取的两种形态-mimetype) 显式给出，避免 list 阶段 hint 与 read 阶段事实来源冲突。

---

## DPE 内容标准格式

DPE 协议**统一规定**通过 Resolver 输出的访问 URI 拉到的内容**MUST 符合 DPE 标准 JSON 格式**——这是 DPE 跨 MCP Server 与跨业务实现互操作的基础（Agent SDK 用同一套解析器处理来自任意 Resolver 的内容）。

完整字段定义见 [DPE 标准化提案](dpe-standardization-proposal.md)（含 Document / DocPage / DocElement 三层完整字段、19 种 Element 类型的判别联合体、TFElementMetadata 40+ 字段、坐标系等）。本节列出协议层 **MUST** 遵守的顶级结构。

### Document JSON（顶级结构）

Resolver 输出的访问 URI 拉到的内容 **MUST** 是一个 JSON 对象，对应 Document 层：

```json
{
  "doc_ref": "rpt-2026",
  "uri": "dpe://com.example.docs/rpt-2026",
  "file_uri": "file:///data/reports/2026-annual.xlsx",
  "file_type": "xlsx",
  "title": "2026 年度报告",
  "summary": "...",
  "page_count": 12,
  "keywords": ["财务", "年报"],
  "last_modified": "2026-01-15T08:30:00Z",
  "pages": [...]
}
```

`pages` 数组**必需**——按阅读顺序排列的 Page 对象。其余字段语义参照 Resource 元数据（值应与 `Resource._meta` / `annotations` 保持一致；MCP Server 实现时建议从同一数据源填充避免漂移）。

### Page 对象

`Document.pages` 数组的每个元素是 Page 对象，对应 DocPage 层。业务方可二选一两种模式：

**模式 A — 内嵌**（适合中小文档，一次拉取完整）：

```json
{
  "page_index": 0,
  "title": "概览",
  "doc_ref": "rpt-2026",
  "elements": [...]                        // 直接含 Element 对象数组
}
```

**模式 B — manifest**（适合大文档，按需加载）：

```json
{
  "page_index": 0,
  "title": "概览",
  "doc_ref": "rpt-2026",
  "uri": "https://oss/.../doc-1/page-0.json",   // 独立 URI 指向页面 JSON
  "element_count": 8                            // 摘要 hint
}
```

Page 对象 **MUST** 包含 `elements` 或 `uri` 之一；两者都可以同时存在（Agent 优先用内嵌的 elements，缺失时按 uri fetch）。Agent SDK 拉 Page URI 后拿到的内容**仍是一个 Page 对象**（含 elements 数组），递归解析。

### Element 对象

`Page.elements` 数组的每个元素是 Element 对象，对应 DocElement 层：

```json
{
  "element_id": "tbl-001",
  "category": "Table",
  "text": "...",
  "doc_ref": "rpt-2026",
  "page_index": 0,
  "ele_metadata": {...}
}
```

- `category` 是判别联合体的鉴别器，遵循 [DPE 提案 § 3.3.1](dpe-standardization-proposal.md) 的 19 种标准类型（Title / NarrativeText / Table / Image / ListItem / CodeSnippet / ...）
- `ele_metadata` 含 40+ 字段（结构关系、空间坐标、视觉信息等），详见 [DPE 提案 § 3.4](dpe-standardization-proposal.md)
- 允许业务自定义 `category`——Agent SDK **SHOULD** 实现"未识别 category 当作通用 TextElement 处理"的兼容性策略

Element 对象一般**不**单独通过 URI 暴露（粒度过细，HTTP 开销不划算）；如业务确有需要，可在 ele_metadata 中携带 `external_uri` 字段供 Agent 按需拉取，**但这是业务层扩展，协议不规定**。

### A2C 协议规定 vs 业务自决

| 范畴 | A2C 协议规定 | 业务自决 |
|------|-------------|---------|
| 顶级结构 | Document / Page / Element 三层 + 必需字段 | — |
| `category` 鉴别器 | 19 种标准类型必须支持 | 可扩展自定义类型 |
| Page 投递模式 | 至少满足"内嵌 elements 或 manifest URI 之一" | 选哪种、混用 |
| JSON 是否压缩 | — | 业务自决 |
| URL 路径风格 / 签名 / 过期 | — | 业务自决 |
| 元数据扩展字段 | — | `extra="allow"`，可加业务字段 |

---

## DPE 文档读取的两种形态（mimetype）

DPE 文档的 `resources/read` 响应**MUST** 使用以下两种 A2C 协议私有 mimetype 之一，按文档大小 / 存储形态自决：

| mimetype | 形态 | text 字段内容 | 适用场景 |
|----------|------|---------------|----------|
| `application/vnd.a2c.dpe-inline+json` | **结构化 inline** | DPE 标准 JSON（[Document 层完整内容](#dpe-内容标准格式)） | 小文档（< 1MB 量级），可直接 inline 走 Socket.IO 不会触及 MCP base64 上限 |
| `application/vnd.a2c.dpe-uri+json` | **URI 引用** | JSON 对象 `{uri, mime_type, size, expires_at?, etag?}` | 大文档 / 已在外部存储（OSS / 文件系统），避免 base64 编码与传输瓶颈 |

### MCP Server 形态选择策略

MCP Server **SHOULD** 基于 `Resource.size` 阈值（典型 1MB）自决用哪种 mimetype：

```python
@server.read_resource()
async def read_resource(uri: str):
    if estimated_size < 1_000_000:
        # 小文档 inline
        return ReadResourceResult(contents=[
            TextResourceContents(
                uri=uri,
                mimeType="application/vnd.a2c.dpe-inline+json",
                text=json.dumps({"doc_ref": ..., "pages": [...]}),
            )
        ])
    else:
        # 大文档走 URI 引用
        return ReadResourceResult(contents=[
            TextResourceContents(
                uri=uri,
                mimeType="application/vnd.a2c.dpe-uri+json",
                text=json.dumps({
                    "uri": "https://oss.example.com/.../doc-1.bin",
                    "mime_type": "application/pdf",
                    "size": 12_345_678,
                    "expires_at": "2026-04-27T12:00:00Z",
                }),
            )
        ])
```

### 校验

- Computer **MUST** 拒绝任何**非** `application/vnd.a2c.dpe-inline+json` / `application/vnd.a2c.dpe-uri+json` 的 mimetype——返回 `4013 DPE Resolution Failed` + `category=invalid_dpe_mime`
- Computer **不校验** URI 引用形态中 `uri` 的可达性（业务策略点，由 Resolver 自决是否预 HEAD 探测）

---

## DPE Resolver Hook（业务层）

### 角色

DPE Resolver 是 Computer 业务层注册的 **hook**——本质上是**对 MCP Server 提供的资源进行二次加工**：把"Agent 想读的 DPE URI"映射到"Agent 可以访问的 URI"，避免大文件直送或存储位置 Agent 不可达造成的问题。类比 [Server 的 ConnectAuth handler](data-structures.md#auth-对象业务层connectauth)：协议层留出口子、业务层填实现。

### 接口契约（语言无关）

Resolver 的签名以**语言无关契约**描述：

```
resolve(
  resource: A2CResource,           # 原始 DPE Resource，uri = dpe://...
  contents: ResolverContents,       # 解析后的内容形态（来自 resources/read）
  hint: ResolverHint,               # 协议级运行时上下文
) -> A2CResource                    # 新 Resource，uri = Agent 可访问 URI（任意 scheme）
```

具体语言绑定由各 SDK 自行决定（Python `Protocol` / Rust `trait` / TypeScript `interface`）。SDK 实现 **MUST** 满足以下行为契约：

1. 同步或异步调用都允许，由 SDK 自决（python-sdk 同时支持 sync/async；rust-sdk 默认 async）
2. 抛出异常 / Err → Computer 转换为 `4013 DPE Resolution Failed` + `category=resolver_error`
3. 返回的 `A2CResource` 字段满足 [data-structures.md 中 A2CResource 的 schema](data-structures.md#a2cresource)

### 类型定义

`A2CResource` / `ResolverContents` / `ResolverHint` 完整 schema 见 [data-structures.md](data-structures.md#dpe-文档相关结构)。`A2CResource` 结构镜像 MCP Resource，但字段命名沿用 A2C snake_case 风格：

```python
class A2CResource(TypedDict, total=False):
    uri: str                              # 必选
    name: NotRequired[str]
    description: NotRequired[str]
    mime_type: NotRequired[str]
    size: NotRequired[int]
    annotations: NotRequired[dict]
    _meta: NotRequired[dict]              # _meta.expires_at / _meta.etag 等承载于此
```

`ResolverContents` 是判别联合类型：

```python
# Inline 形态：MCP Server 返回 application/vnd.a2c.dpe-inline+json
class InlineContents(TypedDict):
    kind: Literal["inline"]
    document: dict                        # DPE 标准 JSON

# External 形态：MCP Server 返回 application/vnd.a2c.dpe-uri+json
class ExternalContents(TypedDict, total=False):
    kind: Literal["external"]
    uri: str                              # 必选：物理存储 URI
    mime_type: NotRequired[str]
    size: NotRequired[int]

ResolverContents = Union[InlineContents, ExternalContents]
```

`ResolverHint` 携带运行时上下文（业务侧审计需要）：

```python
class ResolverHint(TypedDict, total=True):
    mcp_server_name: str                  # 必选：Computer 已经路由过的 server 名
    agent: str                            # 必选：发起请求的 Agent name
    req_id: str                           # 必选：协议级 req_id
```

### Python 示例（仅作 reference impl）

```python
from typing import Protocol

class DPEResolver(Protocol):
    async def resolve(
        self,
        resource: A2CResource,
        contents: ResolverContents,
        hint: ResolverHint,
    ) -> A2CResource:
        ...
```

> **注**：协议规范不再为 Rust / TypeScript 等其他 SDK 提供并列示例——Python 仅作 reference impl，其他 SDK 实现细节由各 SDK 自行决定（参考 A2CResource / ResolverContents / ResolverHint 中性 schema 即可）。

### 实现自由度

业务方完全自决 hook 行为：

- **拿到 Inline 内容** → 重新打包 / 加密 / 上传业务 OSS，输出 https URL
- **拿到 External URI** → 直接转存（不阻塞 stdio）/ 重新签名 / 信任原 URI 直传 Agent
- **缓存命中** → 直接返回历史 URL
- **自定义 scheme** → 返回 `oss://` / `s3://` / 业务私有 scheme（Agent 端需要对应解析器）

### URI 生命周期与可用性

**协议不规定** Resolver 输出 URI 的过期、刷新、可用性、签名机制——这些**全由业务方自决**。Resolver 输出的 `A2CResource` 可在 `_meta` 中携带访问层 hint：

| 字段 | 类型 | 语义 |
|------|------|------|
| `_meta.expires_at` | ISO 8601 字符串 | URI 过期时间；缺省视为不过期 |
| `_meta.etag` | 字符串 | 内容指纹；Agent 多次拉取时校验一致性 |

不再使用 `cacheable` 字段——`expires_at` 缺省即"session 内可缓存"，语义已覆盖。

Agent 行为约束：

- 拿到过期 URI 怎么办 → Agent **MUST** 重新调 `client:get_dpe` 拿新 URI
- URI 安全性、签名、防猜枚举 → 业务方实现责任
- Agent **MUST NOT** 跨 session 缓存 URI——即使看起来是公网持久 URL，下个 session 应重新调 `get_dpe`

### 部署示例

| 场景 | Resolver 实现 | 输出 URI 形态 |
|---|---|---|
| Agent 与 Computer 同机 | 写本地缓存目录 | `file:///var/cache/a2c/doc-1.json` |
| Agent 与 Computer 跨机（公司内网）| 上传 MinIO | `https://minio.internal/.../doc-1.json?X-Signature=...` |
| Agent 与 Computer 跨广域网 | 上传公共 OSS | `https://oss.example.com/.../doc-1.json?X-Auth=...` |
| 多 Agent 共享访问 | 上传到带 ACL 的 S3 | `s3://bucket/key`（Agent 端集成 SDK）|

### 未注册 Resolver 的行为

Computer **MUST NOT** 在未注册 DPE Resolver 时自行降级（如 inline 透传 ResourceContents）——这违背了"Socket.IO 不承载大体量 DPE"的设计意图。

收到 `client:get_dpe` 时若无 Resolver：
- Computer **MUST** 返回错误码 [`4011 DPE Resolver Not Configured`](error-handling.md#dpe-resolver-未配置4011)
- 不进行任何 inline 兜底

### Resolver 缓存与上游变更监听（业务自决）

Resolver 在生产环境通常需要处理：

- **缓存**：相同 dpe URI 的转换结果是否复用？过期多久？
- **上游变更**：MCP Server 发出 `notifications/resources/list_changed` 或 `ResourceUpdatedNotification` 时，是否失效相关缓存、清理过期对象？
- **预热**：Computer 启动时是否预先转换部分文档加速首次访问？

A2C 协议**不规定**这些行为——全部交给 Computer SDK 在自身版本规划里**着情安排**。协议层只规定"行为约束"（resolve 的输入输出契约、未注册时返回 4011），具体实现是否做内存缓存、是否监听上游变化主动失效，全部 SDK 自由发挥。

---

## 文档发现

A2C 协议通过组合 [`client:get_config`](events.md#clientget_config) 和 [`client:get_resources`](events.md#clientget_resources) 两个事件实现 DPE 文档发现，**无需业务方在 MCP Server 上写专门的发现工具**。

### 发现流程

```
1. Agent → client:get_config(computer)
   ← 拿到 MCPServerConfig 字典（key 为 server names）

2. 对每个 server name：
   Agent → client:get_resources(mcp_server=name, cursor=None)
   ← {resources, next_cursor}
   while next_cursor: 继续翻页

3. Agent 自己过滤：
   - 按 scheme（dpe:// / window:// / 业务自定义）
   - 按 _meta / annotations 字段
   - 按名称 / 描述模糊匹配
   - 任意业务条件

4. Agent → client:get_dpe(uri=dpe://...) → 拿到访问 URI → 应用层 fetch
```

### 设计原则

- Computer 是 MCP `resources/list` 的**透明转发层**——不做 scheme / 元数据过滤、不做跨 Server 聚合
- **MCP 标准 cursor 翻页**直接透传——Agent 按需翻页，不强制全量加载
- 业务方拿到 Resource 后**自决过滤**逻辑——这是业务层关注点，不在协议层
- `mcp_server` 必填——保持 Computer 的透明转发原则；想跨 Server 聚合是 Agent 的工作

### Agent 端典型代码

```python
async def discover_dpe(agent, computer):
    """跨所有 MCP Server 发现 dpe 文档。"""
    cfg = await agent.get_config(computer)
    docs = []
    for server_name in cfg["servers"]:
        cursor = None
        while True:
            ret = await agent.get_resources(computer, mcp_server=server_name, cursor=cursor)
            for r in ret["resources"]:
                if r["uri"].startswith("dpe://"):
                    docs.append({
                        "uri": r["uri"],          # 自包含寻址凭据，后续 get_dpe 直接用
                        "title": r.get("name"),
                        "summary": r.get("description"),
                        "page_count": (r.get("_meta") or {}).get("page_count"),
                    })
            cursor = ret.get("next_cursor")
            if not cursor:
                break
    return docs


async def open_dpe(agent, computer, dpe_uri):
    """对任意 dpe URI 调 get_dpe；URI 自包含足够的路由信息。"""
    ret = await agent.get_dpe(computer, uri=dpe_uri)
    return ret["uri"]   # 业务 Resolver 输出的访问 URI；Agent 用应用层协议自取
```

### 资源缓存与发现优化（SDK 自决）

Computer / Agent 端的资源缓存策略、发现性能优化、`resources/list_changed` 监听响应等**由 SDK 在自身版本规划里着情安排**——协议层不强制。SDK 实现可以：

- 缓存 `resources/list` 结果加速重复发现
- 监听 MCP `notifications/resources/list_changed` 主动失效缓存
- 预加载常用 server 的资源列表

但这些都是 SDK 实现选择，不进协议规范。

### 未来：Finder MCP Server

当业务做了多个发现/检索/聚合需求后，常见模式（跨 Server 聚合、过滤、排序、搜索）会沉淀成事实标准。届时可独立开发 **Finder MCP Server**——可插拔的内置 MCP Server，与协议核心解耦。它对 Agent 通过标准 MCP 工具暴露能力，不需要新协议事件。

---

## client:get_dpe 事件

### 概述

Agent 调用 `client:get_dpe` 把一个 DPE URI 转成可访问的 URI。这是 A2C 协议中**唯一的 DPE 内容访问入口**。

```
Agent ──[client:get_dpe]──→ Server ──[路由]──→ Computer
                                              │
                                              ▼
                                         DPE Resolver
                                              │
                                              ▼
                                          访问 URI
       ◄────────[GetDPERet]─────────────┘
       │
       ▼
  Agent 用应用层协议（HTTP/file/...）自取访问 URI 内容
```

### 请求 / 响应

```python
class GetDPEReq(AgentCallData, total=True):
    agent: str            # Agent 名称
    req_id: str           # 请求 ID
    computer: str         # 目标 Computer
    uri: str              # dpe://host/doc-ref（doc-ref 可单段或分段路径）
    timeout: NotRequired[int]  # 秒，默认实现自定


# GetDPERet = A2CResource + req_id（A2CResource 字段集见 data-structures.md）
class GetDPERet(A2CResource, total=False):
    req_id: str           # A2C 协议级关联字段
```

> `GetDPERet` 内容字段完全等同 `A2CResource`——Resolver 是 MCP Resource 的二次加工器，输入输出同形（uri 从逻辑标识转为物理访问地址）。访问层 hint（过期时间、内容指纹）通过 `_meta.expires_at` / `_meta.etag` 承载。完整 schema 见 [data-structures.md](data-structures.md#a2cresource)。

DPE URI 是**自包含寻址凭据**——URI 字符串本身已足够精确定位一个 DPE 文档资源，Agent 拿到任意 dpe URI（无论来自 `client:get_resources` / 业务工具调用返回 / 用户输入 / 跨 session 引用）都可直接调 `get_dpe`。

### Computer 处理流程

1. 接收 `client:get_dpe(uri=dpe://...)`
2. 校验 URI 合法性（参见 [URI 校验规则](#校验规则)）；非法返回 `4012 Invalid DPE URI`；含 query / fragment 时按 [分层处理](#uri-query--fragment-处理分层) 容错丢弃 + WARN
3. 检查是否注册了 DPE Resolver；未注册返回 `4011 DPE Resolver Not Configured`
4. 解析 URI → 通过 `host` 反查 MCP Server（详见 [host 路由策略](#host-路由策略)）；找不到匹配的 MCP Server 返回 `4014 MCP Server Not Found`；MCP Server 未声明 `resources` capability 返回 `4015 MCP Capability Not Supported`
5. 调指定 MCP Server 的 `resources/read(uri)` → 拿 `ReadResourceResult`
6. 解析 mimetype（[详见双 mimetype 章节](#dpe-文档读取的两种形态-mimetype)）：
    - `application/vnd.a2c.dpe-inline+json` → 解析 text 为 DPE 标准 JSON → 构造 `ResolverContents.Inline`
    - `application/vnd.a2c.dpe-uri+json` → 解析 text 为 URI 引用 JSON → 构造 `ResolverContents.External`
    - 其他 mimetype → 返回 `4013 DPE Resolution Failed` + `category=invalid_dpe_mime`
7. 从 list 阶段缓存取出原始 `Resource` → 构造 `A2CResource` 入参
8. 调 Resolver `resolve(resource, contents, hint)` 拿新 `A2CResource`；Resolver 抛异常 → `4013` + `category=resolver_error`；返回值字段非法 → `4013` + `category=resolver_returned_invalid`
9. 把 Resolver 输出包装为 `GetDPERet`（追加 `req_id`），返回给 Agent

### Agent 处理流程

1. 通过任意方式得到 dpe URI（`client:get_resources` 返回 / MCP 工具返回 / 用户输入 / 历史持久化等等）
2. 调 `client:get_dpe(uri)`
3. 拿到访问 URI 后，用对应 scheme 的应用层协议拉取内容：
    - `https://` / `http://` → HTTP GET（推荐 SDK 内置）
    - `file://` → 本地文件读取（推荐 SDK 内置）
    - 其他 scheme（`oss://` / `s3://` / 业务自定义）→ Agent 端需要对应解析器
4. 拉取失败（含 URI 过期）→ 重新调 `client:get_dpe(uri)`

### 错误处理

| 错误码 | 触发场景 |
|---|---|
| [`4011 DPE Resolver Not Configured`](error-handling.md#dpe-resolver-未配置4011) | Computer 未注册 Resolver |
| [`4012 Invalid DPE URI`](error-handling.md#无效-dpe-uri4012) | URI 不符合 dpe scheme 规范（构造层硬错误）|
| [`4013 DPE Resolution Failed`](error-handling.md#dpe-解析失败4013) | Resolver / 上游 / mimetype 失败——payload 内 `category` 字段细分（`upstream_unavailable` / `invalid_dpe_mime` / `resolver_error` / `resolver_returned_invalid`）|
| [`4014 MCP Server Not Found`](error-handling.md#mcp-server-not-found4014) | URI 中的 host 反查不到对应 MCP Server |
| [`4015 MCP Capability Not Supported`](error-handling.md#mcp-capability-not-supported4015) | MCP Server 已注册，但未声明 `resources` capability |

详见 [错误处理](error-handling.md)。

---

## 与 MCP 生态的关系

### MCP Server 实现指引

MCP Server 暴露 DPE 文档时**不需要任何 SMCP 特定代码**——按 MCP 标准 `resources/list` + `resources/read` 实现即可：

```python
@server.list_resources()
async def list_resources():
    return [
        Resource(
            uri="dpe://com.example.docs/rpt-2026",
            name="2026 年度报告",
            description="2026 年度财务与运营报告",
            mimeType="application/json",
            annotations=Annotations(
                audience=["user"],
                lastModified="2026-01-15T08:30:00Z",
            ),
            _meta={
                "keywords": ["财务", "年报"],
                "file_type": "xlsx",
                "page_count": 12,
            },
        ),
    ]


@server.read_resource()
async def read_resource(uri: str):
    # MCP Server 接收 dpe URI（仅 Document 一层，无子路径），返回符合 DPE 标准的 ResourceContents
    # 内容必须符合 DPE 标准 JSON 格式（含 pages 数组），见 [DPE 内容标准格式]
    return ReadResourceResult(contents=[
        TextResourceContents(
            uri=uri,
            mimeType="application/json",
            text=json.dumps({
                "doc_ref": ...,
                "uri": uri,
                "title": ...,
                "page_count": ...,
                "pages": [...]   # 内嵌或 manifest 模式
            }),
        )
    ])
```

**A2C 协议规定** DPE 内容顶级结构（Document → Pages → Elements），见 [DPE 内容标准格式](#dpe-内容标准格式)。详细字段参见 [DPE 标准化提案](dpe-standardization-proposal.md)。

### Computer 实现指引

Computer SDK 提供 Resolver 注册接口：

```python
# 业务方实现 Resolver（Python reference impl）
class MyOSSResolver:
    async def resolve(
        self,
        resource: A2CResource,         # 原始 DPE Resource，uri = dpe://...
        contents: ResolverContents,     # Inline | External
        hint: ResolverHint,
    ) -> A2CResource:
        if contents["kind"] == "inline":
            # 小文档：业务侧重新打包后上传到 OSS
            payload = json.dumps(contents["document"]).encode()
            url = await oss_client.put_object(bucket="a2c-docs", key=f"{resource['uri']}.json", body=payload)
            return {
                "uri": url,
                "mime_type": "application/json",
                "size": len(payload),
                "_meta": {"expires_at": "2026-04-27T13:00:00Z"},
            }
        else:
            # 大文档：信任原 URI 直传，或重新签名/转存
            return {
                "uri": contents["uri"],
                "mime_type": contents.get("mime_type"),
                "size": contents.get("size"),
            }


# Computer 启动时注册
computer.register_dpe_resolver(MyOSSResolver())
```

Computer **MUST NOT** 在未注册 Resolver 时自行降级。
