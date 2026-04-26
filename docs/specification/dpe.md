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
dpe://{host}/{doc-ref}[/sub-path]
```

DPE URI 是**纯标识符**，**不携带任何 query 参数**——所有元数据通过 MCP Resource 的 `_meta` / `annotations` 声明（见 [DPE Resource 元数据](#dpe-resource-元数据)）。

### 组成部分

| 组件 | 必填 | 说明 | 约束 |
|------|------|------|------|
| `scheme` | 是 | 固定 `dpe` | 必须为 `dpe`，否则解析失败 |
| `host` | 是 | MCP Server 唯一标识 | 不能为空；**在同一 Computer 进程范围内 MUST 全局唯一**（跨 Office/Room 也唯一）；推荐反向域名风格，如 `com.example.mcp` |
| `doc-ref` | 是 | 文档引用键（MCP Server 分配的不透明短键） | URL-safe 或 URL-encoded；**不允许**缺省 |
| `sub-path` | 否 | 文档内导航路径 | `pages/{N}` 或 `elements/{ID}` |

### 三级寻址语言

DPE URI 子路径形态为 Agent 提供**结构化定位语言**：

```
Level 1: dpe://host/doc-ref                → 整个文档
Level 2: dpe://host/doc-ref/pages/{N}      → 文档第 N 页
Level 3: dpe://host/doc-ref/elements/{ID}  → 特定元素
```

| 级别 | URI 示例 | 语义 |
|------|---------|---------|
| Level 1 | `dpe://com.example.docs/rpt-2026` | 整个文档 |
| Level 2 | `dpe://com.example.docs/rpt-2026/pages/0` | 第 0 页 |
| Level 3 | `dpe://com.example.docs/rpt-2026/elements/tbl-001` | 元素 ID `tbl-001` |

**协议不规定每层级返回什么内容**——由 DPE Resolver（业务层）决定每层映射到什么访问 URI。常见做法：Level 1 返回完整文档、Level 2 返回单页内容、Level 3 返回单元素详情，但业务方可自由选择支持哪些层级。

### 校验规则

1. `scheme` 必须为 `dpe`
2. `host` 不能为空，且在同一 Computer 进程范围内 **MUST** 全局唯一（与 `window://` 共享 host 命名空间约束，详见 [Window URI 规范](desktop.md#window-uri-规范)）
3. `doc-ref` 必须存在；`dpe://host` 形式（无 doc-ref）视为无效
4. `sub-path` 若存在，必须匹配 `pages/{非负整数}` 或 `elements/{非空字符串}`
5. DPE URI **不允许**携带 query 参数；若解析时检测到 query，应记录 WARN 并丢弃 query 部分

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

## DPE Resolver Hook（业务层）

### 角色

DPE Resolver 是 Computer 业务层注册的 **hook**——把"Agent 想读的 DPE URI"转成"Agent 可以访问的 URI"。类比 [Server 的 ConnectAuth handler](data-structures.md#auth-对象业务层connectauth)：协议层留出口子、业务层填实现。

### 接口契约

```python
class DPEResolver(Protocol):
    async def resolve(
        self,
        dpe_uri: str,                # Agent 请求的 dpe URI（含 sub-path）
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
    uri: str              # dpe://host/doc-ref[/pages/N | /elements/ID]
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
    # 按 dpe URI 子路径返回对应内容
    # 内容形态由 MCP Server 自决——A2C 协议不规定 JSON schema
    if uri == "dpe://com.example.docs/rpt-2026":
        return ReadResourceResult(contents=[
            TextResourceContents(uri=uri, mimeType="application/json", text=...)
        ])
    elif uri.startswith("dpe://com.example.docs/rpt-2026/pages/"):
        ...
```

**A2C 协议不规定 DPE 内容的 JSON schema**——Level 1/2/3 各级返回什么具体内容由 MCP Server 与 Agent 之间的应用层契约决定（业界可基于 [DPE 标准化提案](dpe-standardization-proposal.md) 形成事实标准）。

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
