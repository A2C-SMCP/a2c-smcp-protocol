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
- **Agent 端**：调用 `client:open_dpe` 拿到访问 URI，用应用层协议（HTTP / file / ...）拉取实际内容；DPE 内容形态由文档应用层决定，A2C 协议不规定

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
| `host` | 是 | MCP Server 唯一标识 | 不能为空；**在同一 Computer 进程范围内 MUST 全局唯一**（跨 Office/Room 也唯一）；推荐反向域名风格，如 `com.example.mcp` |
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
2. `host` 不能为空，且在同一 Computer 进程范围内 **MUST** 全局唯一（与 `window://` 共享 host 命名空间约束，详见 [Window URI 规范](desktop.md#window-uri-规范)）
3. `doc-ref` 必须存在且至少含一段非空内容；`dpe://host` 或 `dpe://host/` 形式（doc-ref 为空）视为无效
4. 每段 path 允许 URL 编码（`a%2Fb` 在单段内解码为 `a/b`，与"段间 `/`"语义区分）
5. DPE URI **不允许**携带 query 参数或 fragment；解析时检测到 query/fragment 应记录 WARN 并丢弃

### URI 示例

```
dpe://com.example.docs/rpt-2026                      # 单段不透明键
dpe://com.example.docs/reports/2026/annual           # 三段层级路径
dpe://com.example.code/src/main/java/Foo.java        # 含扩展名的代码路径
dpe://com.example.mail/inbox/2026-01-15/email-abc    # 时间分段
```

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
| `_meta.file_uri` | `str` | 否 | 原始文件 URI（如 `file:///data/reports/xxx.xlsx`）|

### 校验规则

1. `_meta.page_count` 若存在，**MUST** 为正整数（≥ 1）。单页文档约定 `page_count=1`；`0` 与 missing 视为无效（Agent 无法规划翻页，但仍可走 `open_dpe(dpe://host/doc-ref)` 拿整文档 URI）
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
        "file_uri": "file:///data/reports/2026-annual.xlsx",
    },
)
```

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

## DPE Resolver Hook（业务层）

### 角色

DPE Resolver 是 Computer 业务层注册的 **hook**——把"Agent 想读的 DPE URI"转成"Agent 可以访问的 URI"。类比 [Server 的 ConnectAuth handler](data-structures.md#auth-对象业务层connectauth)：协议层留出口子、业务层填实现。

### 接口契约

```python
class DPEResolver(Protocol):
    async def resolve(
        self,
        dpe_uri: str,                # Agent 请求的 dpe URI（dpe://host/doc-ref）
        contents: list[ResourceContents],  # Computer 已从 MCP Server 读到的内容
        hint: ResolverHint,          # mcp_server_name, mime_type 等上下文
    ) -> ResolvedResource:
        """把 DPE Resource 转成可访问的 URI。"""


class ResolverHint(TypedDict, total=False):
    mcp_server_name: str
    mime_type: NotRequired[str]


class ResolvedResource(TypedDict, total=False):
    uri: str                     # 可访问 URI（任意 scheme：https / file / 业务自定义）
    mime_type: NotRequired[str]
    size: NotRequired[int]       # 字节数；可选 hint，给 Agent 决策预算
```

### 实现自由度

业务方完全自决 hook 行为：

- **上传到对象存储** → 返回预签名 https URL
- **写入本地共享路径** → 返回 `file://...`（Agent 同机部署时）
- **缓存命中** → 直接返回历史 URL
- **自定义 scheme** → 返回 `oss://` / `s3://` / 业务私有 scheme（Agent 端需要对应解析器）

业务方可以决定**不实际读取** `contents` 入参——比如基于 dpe URI 直接构造 file URI 指向 MCP Server 已知物理路径，跳过中转。

### URI 生命周期与可用性

**协议不规定** Resolver 输出 URI 的过期、刷新、可用性、签名机制——这些**全由业务方自决**：

- URI 是否过期、过期多久 → 业务方决定
- Agent 拿到过期 URI 怎么办 → Agent **MUST** 重新调 `client:open_dpe` 拿新 URI
- URI 安全性、签名、防猜枚举 → 业务方实现责任
- URI 校验、checksum → 业务方可选（在 `ResolvedResource` 里返回 hint，Agent 自行校验）

Agent **MUST NOT** 跨 session 缓存 URI——即使看起来是公网持久 URL，下个 session 应重新调 `open_dpe`。

### 部署示例

| 场景 | Resolver 实现 | URI 形态 |
|---|---|---|
| Agent 与 Computer 同机 | 写本地缓存目录 | `file:///var/cache/a2c/doc-1.json` |
| Agent 与 Computer 跨机（公司内网）| 上传 MinIO | `https://minio.internal/.../doc-1.json?X-Signature=...` |
| Agent 与 Computer 跨广域网 | 上传公共 OSS | `https://oss.example.com/.../doc-1.json?X-Auth=...` |
| 多 Agent 共享访问 | 上传到带 ACL 的 S3 | `s3://bucket/key`（Agent 端集成 SDK）|

### 未注册 Resolver 的行为

Computer **MUST NOT** 在未注册 DPE Resolver 时自行降级（如 inline 透传 ResourceContents）——这违背了"Socket.IO 不承载大体量 DPE"的设计意图。

收到 `client:open_dpe` 时若无 Resolver：
- Computer **MUST** 返回错误码 [`4011 DPE Resolver Not Configured`](error-handling.md#dpe-resolver-未配置4011)
- 不进行任何 inline 兜底

---

## client:open_dpe 事件

### 概述

Agent 调用 `client:open_dpe` 把一个 DPE URI 转成可访问的 URI。这是 A2C 协议中**唯一的 DPE 内容访问入口**。

```
Agent ──[client:open_dpe]──→ Server ──[路由]──→ Computer
                                              │
                                              ▼
                                         DPE Resolver
                                              │
                                              ▼
                                          访问 URI
       ◄────────[OpenDPERet]─────────────┘
       │
       ▼
  Agent 用应用层协议（HTTP/file/...）自取访问 URI 内容
```

### 请求 / 响应

```python
class OpenDPEReq(AgentCallData, total=True):
    agent: str            # Agent 名称
    req_id: str           # 请求 ID
    computer: str         # 目标 Computer
    uri: str              # dpe://host/doc-ref（doc-ref 可单段或分段路径）
    timeout: NotRequired[int]  # 秒，默认实现自定


class OpenDPERet(TypedDict, total=False):
    uri: str              # Resolver 输出的访问 URI
    mime_type: NotRequired[str]
    size: NotRequired[int]
    req_id: str
```

### Computer 处理流程

1. 接收 `client:open_dpe(uri=dpe://...)`
2. 校验 URI 合法性（参见 [URI 校验规则](#校验规则)）；非法返回 `4012 Invalid DPE URI`
3. 检查是否注册了 DPE Resolver；未注册返回 `4011 DPE Resolver Not Configured`
4. 解析 URI → 定位对应 MCP Server（按 `host` 找 Server）
5. 调 MCP Server 的 `resources/read(uri)` 拿 `ResourceContents`
6. 调 Resolver `resolve(uri, contents, hint)` 拿 `ResolvedResource`
7. 返回 `OpenDPERet` 给 Agent

### Agent 处理流程

1. 通过任意方式得到 dpe URI（MCP 工具返回、用户输入、未来的 Finder MCP Server 列出等等）
2. 调 `client:open_dpe(uri)`
3. 拿到访问 URI 后，用对应 scheme 的应用层协议拉取内容：
    - `https://` / `http://` → HTTP GET（推荐 SDK 内置）
    - `file://` → 本地文件读取（推荐 SDK 内置）
    - 其他 scheme（`oss://` / `s3://` / 业务自定义）→ Agent 端需要对应解析器
4. 拉取失败（含 URI 过期）→ 重新调 `client:open_dpe`

### 错误处理

| 错误码 | 触发场景 |
|---|---|
| [`4011 DPE Resolver Not Configured`](error-handling.md#dpe-resolver-未配置4011) | Computer 未注册 Resolver |
| [`4012 Invalid DPE URI`](error-handling.md#无效-dpe-uri4012) | URI 不符合 dpe scheme 规范 |
| [`4013 DPE Resolution Failed`](error-handling.md#dpe-解析失败4013) | Resolver 执行抛异常、上传失败、上游 MCP Server 不可用 |

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
                "file_uri": "file:///data/reports/2026-annual.xlsx",
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
# 业务方实现 Resolver
class MyOSSResolver:
    async def resolve(self, dpe_uri, contents, hint):
        # 上传到对象存储
        url = await oss_client.put_object(
            bucket="a2c-docs",
            key=f"{dpe_uri}.json",
            body=contents[0].text,
        )
        return ResolvedResource(
            uri=url,
            mime_type=hint.get("mime_type"),
            size=len(contents[0].text),
        )


# Computer 启动时注册
computer.register_dpe_resolver(MyOSSResolver())
```

Computer **MUST NOT** 在未注册 Resolver 时自行降级。

### 未来：Finder 作为内置 MCP Server

文档发现、检索、聚合视图、跨 MCP Server 文档管理等"管理类"能力**不在 v0.2 协议范围**。这些能力适合作为**内置 MCP Server**实现（暂称"Finder"），通过标准 MCP 工具调用与 DPE URI 暴露给 Agent，与协议核心解耦。

v0.2 不引入 Finder——等 DPE 在多 SDK 中标准化稳定后再独立设计。届时 Finder 作为可插拔模块，不影响协议核心。
