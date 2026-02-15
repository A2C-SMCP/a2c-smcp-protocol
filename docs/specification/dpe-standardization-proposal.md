# DPE (Document-Page-Element) 统一文档表示模型标准化提案

> **版本**: 1.0-draft
> **日期**: 2026-02-14
> **作者**: TFRobot 团队
> **状态**: 提案阶段

---

## 摘要

本提案介绍 **DPE (Document-Page-Element)** 三层文档表示模型——一种面向 AI 系统的统一文档数据结构。DPE 模型以"文档-页面-元素"的三级层次结构，将传统计算机上几乎所有主流文档格式（PDF、Word、Excel、PPT、HTML、邮件、图片、代码仓库等 30+ 种）统一映射到同一套数据模型中，使上层 AI 应用能够以一致的方式读取、检索、推理和操作任意文档内容。

DPE 模型已在 TFRobot 智能体平台中经过工程验证，支撑了从文档解析、向量检索、知识图谱构建到多步推理的完整 AI 处理链路。我们建议将 DPE 结构纳入协议的标准文档表示格式。

---

## 1. 问题背景：为什么需要统一文档模型？

### 1.1 现状：碎片化的文档世界

当今信息世界的文档类型高度碎片化：

| 类别 | 典型格式 | 内容特征 |
|------|----------|----------|
| 排版文档 | PDF, DOCX, ODT, RTF | 页面布局、段落、表格、图片 |
| 演示文稿 | PPTX, PPT | 幻灯片、文本框、图表 |
| 电子表格 | XLSX, CSV, TSV | 工作表、行列、公式 |
| 网页内容 | HTML, XML, Markdown | DOM 结构、链接、多媒体 |
| 通信内容 | EML, MSG | 收发人、主题、正文、附件 |
| 图像文件 | PNG, JPG, TIFF, BMP, HEIC | 像素数据、OCR 文本 |
| 电子书 | EPUB | 章节、目录、正文 |
| 代码仓库 | Python/Java/JS/TS Repo | 文件树、函数、类、注释 |

每种格式都有自己的解析库、数据结构和访问方式。对于需要处理多种文档的 AI 系统来说，这意味着：

- **N 种格式 × M 种 AI 能力 = N×M 种适配逻辑**，组合爆炸
- 每种格式的元数据语义不同（PDF 有"页"，Excel 有"Sheet"，PPT 有"幻灯片"），难以统一检索
- 空间信息表达不一致（PDF 用 Point 坐标系，图片用 Pixel 坐标系），布局分析困难

### 1.2 核心需求

一个好的统一文档模型需要同时满足：

1. **表达力**：能忠实表示各种文档格式的内容与结构，不丢失关键信息
2. **统一性**：上层系统只需面对一套接口，不必关心底层格式差异
3. **可扩展性**：新文档类型或新元数据字段可以无缝加入，不破坏现有结构
4. **AI 友好**：结构天然适配向量检索、文本分片、上下文窗口管理等 AI 工作流
5. **空间感知**：保留文档的布局信息，支持视觉理解和定位

---

## 2. DPE 模型设计

### 2.1 核心直觉：文档的"最大公因数"

DPE 模型的设计出发点是一个简单但深刻的观察：

> **几乎所有文档格式，在概念上都可以拆解为三个层次：一个文档包含若干"页面"，每个页面包含若干"内容元素"。**

- PDF 有物理页面，每页有文本块、图片、表格
- Word 有逻辑页面（通过分页符划分），每页有段落、列表、图片
- PPT 有幻灯片，每张有文本框、图表
- Excel 有工作表（Sheet），每个 Sheet 有单元格和行
- HTML 有节/区块，每个区块有文本、链接、表格
- 邮件有"信"本身作为一个页面，包含发件人、正文、附件
- 图片是单页文档，OCR 后产出文本元素
- 代码仓库有文件（页面），每个文件有函数/类/注释（元素）

这就是 DPE 三层结构的核心直觉——它不是某种文档格式的超集，而是所有文档格式的**语义公因数**。

### 2.2 三层架构

```
┌─────────────────────────────────────────────────┐
│                   Document                       │
│  ┌─────────────────────────────────────────────┐ │
│  │ file_uri: 唯一资源定位                        │ │
│  │ file_type: 源格式枚举 (30+ 种)               │ │
│  │ doc_metadata: 文档级元数据                    │ │
│  │ keywords: 文档级关键词                        │ │
│  │ entrance_page_id: 快速入口指针                │ │
│  └─────────────────────────────────────────────┘ │
│                      │ 1:N                       │
│  ┌─────────────────────────────────────────────┐ │
│  │                   DocPage                     │ │
│  │  number: 页面序号                             │ │
│  │  title: 页面标题                              │ │
│  │  keywords: 页面级关键词                       │ │
│  │  entrance_ele_id: 入口元素指针                │ │
│  └─────────────────────────────────────────────┘ │
│                      │ 1:N                       │
│  ┌─────────────────────────────────────────────┐ │
│  │                 DocElement                    │ │
│  │  text: 内容文本                               │ │
│  │  category: 元素类型 (可判别联合体)             │ │
│  │  element_id: 不可变源 ID (UUID)               │ │
│  │  ele_metadata: 元素级元数据 (40+ 字段)         │ │
│  │  keywords: 元素级关键词                        │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 2.3 设计原则

| 原则 | 实现方式 |
|------|----------|
| **最小惊讶** | 三层结构映射到人对文档的直觉认知——翻开一个文档，翻到某页，看到某段内容 |
| **类型安全** | 全部使用 Pydantic 模型建模，提供严格的类型校验和 JSON Schema |
| **关注点分离** | 内容（text）、结构（category/层级）、位置（coordinates）、语义（metadata）完全正交 |
| **开放-封闭** | 元素类型通过继承扩展（开放），核心三层结构不变（封闭） |
| **格式无关** | 同一个 `Document` 对象，无论来自 PDF 还是 Excel，上层代码一视同仁 |

---

## 3. 模型详细设计

### 3.1 Document 层——文档的"封面"

Document 是整个模型的根节点，承载文档级别的全局信息：

```
Document
├── doc_id: int?          # 持久化主键（数据库自增）
├── file_uri: URL         # 文档的唯一资源标识符（必填）
├── file_type: TFFileType # 源格式枚举
├── keywords: [str]?      # 全文关键词
├── pages: [DocPage]      # 子页面集合
├── entrance_page_id: int?# 入口页面快速指针
└── doc_metadata           # 文档级元数据
    ├── created_at: datetime
    ├── last_modified: datetime
    ├── filename: str?
    ├── summary: str?              # 文档摘要
    ├── languages: [str]?          # 语言列表 (ISO 639-3)
    ├── forward_citation_uris: [URL]?   # 正向引用（谁引用了我）
    ├── backward_citation_uris: [URL]?  # 反向引用（我引用了谁）
    ├── global_dict: {str: str}?   # 全局指代消歧字典
    └── ...（允许自定义扩展字段）
```

**设计亮点**：

- **`file_uri` 作为唯一标识**：采用 URI 而非文件路径，使得本地文件 (`file:///...`)、网络资源 (`https://...`)、对象存储 (`s3://...`) 都能统一寻址。
- **`entrance_page_id` 快速指针**：对于大型文档，直接跳转到最重要的页面，不必遍历全部。
- **`global_dict` 全局指代消歧**：在合同等文档中，"甲方"、"乙方" 这样的指代需要在文档级别统一解析（如 `{"甲方": "北京XX科技有限公司"}`），避免在每个 Element 上重复解析。
- **双向引用链**：`forward/backward_citation_uris` 构建文档间的引用图谱，支持知识关联。

### 3.2 DocPage 层——文档的"帧"

DocPage 是文档内容的组织单元，对应人阅读文档时"翻一页"的直觉：

```
DocPage
├── page_id: int?         # 持久化主键
├── doc_id: int?          # 外键→Document
├── number: int           # 页面序号
├── title: str?           # 页面标题
├── keywords: [str]?      # 页面关键词
├── elements: [DocElement]# 子元素集合（阅读序排列）
└── entrance_ele_id: int? # 入口元素快速指针
```

**为什么需要 Page 这一层？**

这是 DPE 模型与扁平式文档模型（如"文档 → 元素列表"）的核心区别。Page 层的存在解决了三个关键问题：

1. **分页语义的保留**：PDF 的物理页、PPT 的幻灯片、Excel 的工作表——这些"页面"边界本身携带语义信息（作者有意为之的信息分组），扁平化会丢失这一信息。

2. **上下文窗口的天然边界**：LLM 有上下文长度限制。Page 提供了一个自然的、有语义的分片边界——一页内容通常是一个完整的信息单元，既不会太长（超出窗口），也不会太碎（丢失上下文）。

3. **空间坐标系的作用域**：同一页面内的所有元素共享坐标空间（如 PDF 一页的宽高），Page 是坐标系的自然作用域。

**Page 对不同格式的语义映射**：

| 源格式 | Page 的含义 | number 的语义 |
|--------|------------|--------------|
| PDF | 物理页面 | 页码 |
| DOCX | 逻辑页面（分页符分割） | 页序 |
| PPTX | 幻灯片 | 幻灯片序号 |
| XLSX | 工作表 (Sheet) | Sheet 索引 |
| HTML | `<section>` / `<article>` / 逻辑块 | 区块序号 |
| EML | 邮件整体 | 0（单页） |
| Image | 图像自身 | 0（单页） |
| Code Repo | 源文件 | 文件索引 |

### 3.3 DocElement 层——文档的"原子"

DocElement 是 DPE 模型的核心——文档内容的最小语义单元：

```
DocElement (基类)
├── ele_id: int?              # 持久化主键（数据库自增）
├── page_id: int?             # 外键→DocPage
├── text: str                 # 内容文本（可清洗）
├── category: str             # 元素类型标识符（判别联合体的鉴别器）
├── element_id: UUID|str      # 不可变源 ID
├── keywords: [str]?          # 元素关键词
└── ele_metadata               # 元素级元数据 (40+ 字段)
```

#### 3.3.1 判别联合体 (Discriminated Union) —— 类型安全的多态

DPE 模型对元素类型的建模，采用了**以 `category` 为鉴别器的判别联合体**模式。这是整个设计中最精巧的部分之一。

当前已定义的 19 种元素类型：

```
DocElement (抽象基类)
├── TextElement (通用文本)
│   ├── Title               # 标题（支持 category_depth 层级）
│   ├── NarrativeText       # 正文段落
│   ├── ListItem            # 列表项（支持嵌套深度）
│   ├── Address             # 地址信息
│   ├── EmailAddress        # 邮件地址
│   ├── CompositeElement    # 复合块（分片产物）
│   ├── CodeSnippet         # 代码片段
│   ├── FigureCaption       # 图片说明
│   ├── PageNumber          # 页码
│   ├── Formula             # 数学公式
│   ├── Image               # 图片（含 base64/path）
│   ├── PageBreak           # 分页符
│   ├── Table               # 表格（含行列解析）
│   ├── TableChunk          # 表格行块
│   ├── Header              # 页眉
│   ├── Footer              # 页脚
│   └── FormKeysValues      # 表单键值对
└── CheckBoxElement          # 复选框（含 checked 状态）
```

**这种设计的精妙之处**：

1. **统一接口，差异隐藏**：所有元素共享 `text`、`category`、`ele_metadata` 三个核心字段。上层代码可以统一遍历、检索和处理所有元素，只在需要时通过 `category` 鉴别器做特化处理。

2. **类型安全的反序列化**：从 JSON 或数据库反序列化时，工厂方法根据 `category` 字段自动路由到正确的子类，无需外部类型注册表。

3. **开放式扩展**：新增元素类型只需继承 `DocElement` 并声明 `category: Literal["NewType"]`，基类的 `__init_subclass__` 自动完成注册，零配置。

4. **表格的特殊处理**：`Table` 元素内置了行列解析能力——从 HTML 表格或 Markdown 表格中自动提取表头和数据行，并拆分为 `TableChunk`，使得表格内容可以被 LLM 按行理解。

#### 3.3.2 双 ID 系统

DPE 模型为每个元素维护两套 ID：

| ID | 类型 | 来源 | 用途 |
|----|------|------|------|
| `element_id` | UUID/string | 文档解析时生成，不可变 | 元素身份追踪、跨系统引用、parent/related 关系 |
| `ele_id` | 自增整数 | 数据库入库时分配 | 持久化主键、外键关联、排序 |

**为什么需要双 ID？**

`element_id` 是元素的"身份证号"——从文档被解析的那一刻起就确定了，不随存储位置变化。这对于构建元素间的关系图（`parent_id`、`related_ids`）至关重要——在元素尚未入库时就需要能够相互引用。

`ele_id` 是数据库的"工号"——自增整数，高效索引，适合做外键和排序依据。

两者的分离使得 DPE 模型在"文档处理流水线"（不涉及数据库）和"文档存储系统"（需要数据库）两种场景下都能良好运作。

### 3.4 元数据体系——信息不丢失的关键

DPE 模型在三个层级都配备了元数据，其中元素级元数据 (`TFElementMetadata`) 最为丰富，包含 40+ 个语义明确的字段：

```
TFElementMetadata
├── 【文件信息】
│   ├── filename, filetype, last_modified
│   └── encrypted (PDF 加密标识)
│
├── 【结构关系】
│   ├── parent_id: ElementId        # 父元素（树形结构）
│   ├── related_ids: [ElementId]    # 相关元素（图结构）
│   ├── category_depth: int         # 层级深度（标题/列表嵌套）
│   └── is_continuation: bool       # 跨页续接标记
│
├── 【空间位置】
│   └── coordinates                 # 坐标信息
│       ├── points: ((x1,y1), (x2,y2), ...)  # 边界框顶点
│       └── system: CoordinateSystem          # 坐标系
│           ├── PixelSpace (屏幕系，原点左上，y↓)
│           ├── PointSpace (笛卡尔系，原点左下，y↑)
│           └── RelativeCoordinateSystem (归一化，[0,1]²)
│
├── 【视觉信息】
│   ├── text_as_html: str           # HTML 格式保留（表格）
│   ├── image_path / image_base64   # 图像数据
│   ├── image_mime_type             # 图像格式
│   ├── emphasized_text_contents    # 加粗/斜体文本
│   └── detection_class_prob        # AI 检测置信度
│
├── 【语义标记】
│   ├── languages: [str]            # ISO 639-3 语言标识
│   ├── is_active / is_deprecated   # 生命周期状态
│   ├── is_narrative                # 是否正文内容
│   └── header_info                 # 表格表头信息
│
├── 【分页信息】
│   ├── page_number: int            # 源文档页码
│   └── page_name: str              # 工作表名称
│
├── 【邮件专属】
│   ├── sent_from / sent_to         # 收发人
│   └── subject                     # 主题
│
├── 【超链接】
│   ├── link_texts / link_urls      # 链接文本与目标
│   └── links: [{text, url, start_index}]  # 带位置的链接
│
├── 【协作信息】
│   ├── editor / editor_email / editor_id
│   └── data_source                 # 数据源追踪
│
└── ...（extra="allow"，支持任意扩展字段）
```

**设计亮点**：

- **`extra="allow"` 策略**：文档级和元素级元数据都允许额外字段。这意味着特定领域（如医疗、法律、金融）可以在不修改核心模型的情况下附加领域特定的元数据。
- **坐标系统一转换**：不同文档格式使用不同的坐标系（PDF 用 PointSpace，图片用 PixelSpace），DPE 模型内置了坐标系间的线性变换，通过 `RelativeCoordinateSystem` (归一化到 [0,1]²) 作为中间桥梁，实现任意坐标系之间的无损转换。

---

## 4. 设计巧妙之处

### 4.1 "以人的阅读顺序为序"

DocPage 的文档注释中写道：

> *"A page consists of an ordered set of elements. The intent of the ordering is to align with the order in which a person would read the document."*

这是一个看似简单但影响深远的设计决策。Element 在 Page 内的排列不是按照文件格式的存储顺序，也不是按照空间坐标排列，而是按照**人的阅读顺序**。这意味着：

- 对于中文/英文文档：从左到右，从上到下
- 对于阿拉伯语文档：从右到左
- 对于表格：先表头，再逐行
- 对于多栏布局：先左栏从上到下，再右栏

这种排序使得将元素列表直接拼接成文本（`"\n\n".join(elements)`）就能产生可读的内容，极大简化了 LLM 的文本输入构造。

### 4.2 入口指针 (Entrance Pointer)

Document 有 `entrance_page_id`，Page 有 `entrance_ele_id`——这是一对"快速入口"指针。

在大型文档中（如数百页的技术手册），AI 系统往往需要快速定位到"最重要"或"最相关"的内容。入口指针提供了 O(1) 的跳转能力，而不需要遍历全部页面/元素。

这类似于书的"目录"或网页的"锚点"——一个轻量但实用的优化。

### 4.3 可清洗字段 (Cleanable Fields)

DocElement 的 `text` 字段被标记为 `cleanable=True`，配合 `apply(*cleaners)` 方法：

```python
# 链式文本清洗
for element in doc.elements:
    element.apply(str.strip, normalize_unicode, remove_control_chars)
```

这个设计将"文本内容"与"文本清洗"解耦。`apply()` 会自动找到所有标记为 `cleanable` 的字段并依次应用清洗函数，既安全（有类型校验，确保输出仍为字符串）又灵活（清洗策略可以组合和替换）。

### 4.4 Cmd-F 式文档检索

Document 内置了 `lookup()` 和 `lookup_all()` 方法，模拟了 Cmd-F（Ctrl-F）的查找行为：

- `lookup(term)` 返回下一个匹配的元素，连续调用会循环遍历所有匹配项
- `lookup_all(term)` 返回所有匹配元素
- `after_element(el, count)` / `before_element(el, count)` 获取上下文

这为 AI 系统提供了与人类相同的"在文档中查找并获取上下文"的能力——这正是 RAG (Retrieval-Augmented Generation) 工作流中最常用的操作之一。

### 4.5 自注册的类型系统

元素子类通过 `__init_subclass__` 机制自动注册到全局注册表：

```python
class DocElement(TFBaseModel):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        RegisterMap().register("DocElement", cls)
```

这意味着任何系统——包括第三方插件——只要定义了 `DocElement` 的子类，就自动被 DPE 系统识别和支持。无需配置文件、无需手动注册、无需修改核心代码。

### 4.6 坐标系的统一转换桥

DPE 通过 `RelativeCoordinateSystem`（归一化到 [0,1] × [0,1]）作为所有坐标系之间的"通用货币"：

```
PixelSpace ←→ RelativeCoordinate ←→ PointSpace
(图片坐标)      (归一化中间态)         (PDF坐标)
```

任何坐标系只要能与 Relative 互转，就能与其他所有坐标系互转。新增坐标系只需实现两个方向的转换，即获得对所有已有坐标系的兼容性。这是经典的"中间表示"（Intermediate Representation）设计模式在空间域的应用。

### 4.7 独立存储标记 (Independent Storage)

DPE 模型中的关键嵌套对象（`pages`、`elements`、`coordinates`）被标记为 `is_independent_storage=True`：

```python
pages: list[DocPage] = TFField(
    default_factory=list,
    tf_meta=TFFieldMeta(is_independent_storage=True)
)
```

这意味着这些字段在序列化/反序列化时可以**独立于父对象**处理。具体场景：

- 数据库存储时，Document、Page、Element 分别存入三张表
- 文件存储时，大型嵌套可以各自保存到独立文件
- 网络传输时，可以按需懒加载子对象

这种标记使得同一套 Pydantic 模型既能用于内存中的完整对象图操作，又能适配关系型数据库、文件系统、分布式缓存等不同存储后端。

---

## 5. 文档格式覆盖与转换能力

### 5.1 支持的文档格式

DPE 模型通过 `TFFileType` 枚举覆盖了 30+ 种文档格式，每种格式都携带完整的元信息：

| 属性 | 说明 | 示例 |
|------|------|------|
| `partitioner_shortname` | 对应的解析器类名 | `"PDFLoader"`, `"WordLoader"` |
| `importable_package_dependencies` | 所需依赖包 | `["pdf2image", "pdfminer"]` |
| `extensions` | 文件扩展名 | `[".pdf"]`, `[".docx"]` |
| `canonical_mime_type` | 标准 MIME 类型 | `"application/pdf"` |
| `alias_mime_types` | 别名 MIME 类型 | `["text/x-csv", ...]` |

**格式识别策略**：

```python
# 通过扩展名识别
TFFileType.from_extension(".pdf")  → TFFileType.PDF

# 通过 MIME 类型识别
TFFileType.from_mime_type("application/pdf")  → TFFileType.PDF
```

### 5.2 输出格式转换

DPE 模型支持将任意文档格式转换为标准 Markdown 输出，每种元素类型有对应的转换规则：

| 元素类型 | Markdown 输出 |
|----------|--------------|
| Title (depth=2) | `## 标题文本` |
| NarrativeText | 普通段落 |
| ListItem (depth=1) | `  - 列表项` |
| Table | Markdown 表格 或 HTML `<table>` |
| CodeSnippet | `` ```language ... ``` `` |
| Image | `<img src="..." />` |
| CheckBox (checked) | `- [x] 内容` |
| PageBreak | `---` |
| Header/Footer | `> [Header] 文本` |
| Formula | `$公式内容$` |

---

## 6. 存储层设计

### 6.1 关系型数据库映射

DPE 模型可直接映射到三张关系表，支持 PostgreSQL 的高级特性：

```sql
-- 文档表
CREATE TABLE doc.documents (
    doc_id        SERIAL PRIMARY KEY,
    file_uri      VARCHAR(1024) NOT NULL UNIQUE,
    file_type     VARCHAR(32)   NOT NULL,
    keywords      TEXT[],                          -- PostgreSQL 数组
    entrance_page_id INTEGER,
    metadata      JSONB,                           -- 半结构化元数据
    sort_weight   BIGINT,                          -- 游标分页权重
    create_timestamp BIGINT,
    update_timestamp BIGINT
);

-- 页面表
CREATE TABLE doc.doc_pages (
    page_id       SERIAL PRIMARY KEY,
    doc_id        INTEGER NOT NULL REFERENCES documents,
    number        INTEGER NOT NULL,
    title         VARCHAR(128),
    keywords      TEXT[],
    entrance_ele_id INTEGER,
    UNIQUE(doc_id, number)                         -- 文档内页码唯一
);

-- 元素表
CREATE TABLE doc.doc_elements (
    ele_id        SERIAL PRIMARY KEY,
    page_id       INTEGER NOT NULL REFERENCES doc_pages,
    text          TEXT,
    category      VARCHAR(64) NOT NULL,
    keywords      TEXT[],
    element_id    VARCHAR(128) NOT NULL UNIQUE,     -- 源 ID 全局唯一
    metadata      JSONB                            -- 半结构化元数据
);
```

**索引策略**：

- `file_uri` UNIQUE 索引：快速去重和定位
- `category` 索引：按元素类型检索（如"只查表格"）
- `element_id` UNIQUE 索引：跨系统元素追踪
- `metadata` GIN 索引：JSONB 内部字段查询
- `keywords` GIN 索引：数组重叠查询 (`&&` 操作符)

### 6.2 游标分页

三张表都有计算字段 `sort_weight`，实现高性能的游标分页：

```
sort_weight = update_timestamp × 1000 + (id % 1000)
```

这种设计在保证"最近更新优先"排序的同时，通过取模操作避免了相同时间戳的记录产生相同权重。

---

## 7. AI 工作流适配性

### 7.1 向量检索 (RAG)

DPE 模型天然适配 RAG 工作流：

```
Document → Pages → Elements → 向量化 → FAISS/ChromaDB
                                          ↓
                              查询 → 返回 Element → 通过 parent 关系获取上下文
```

- **分片粒度灵活**：可以按 Page 分片（粗粒度）或按 Element 分片（细粒度）
- **元数据过滤**：向量检索时可附加 `category`、`languages`、`page_number` 等元数据过滤条件
- **上下文重建**：`after_element()` / `before_element()` 方法可以从匹配元素扩展到完整上下文

### 7.2 文本分片

内置的 `split_element()` 函数支持智能分片：

- **语言感知**：中文使用 Jieba 分词，英文使用递归字符分割
- **表格特殊处理**：先拆分表头，再逐行拆分，保证表格结构完整性
- **元数据继承**：分片产物继承原始元素的全部元数据（生成新 UUID）

### 7.3 知识图谱

DPE 元素通过 `parent_id` 和 `related_ids` 构建关系网络：

```
element_A (parent_id → element_B)
element_C (related_ids → [element_A, element_D])
```

配合文档级的 `forward/backward_citation_uris`，可以构建从元素级到文档级的多层知识图谱。

---

## 8. 与其他方案的对比

| 特性 | DPE 模型 | Unstructured Element | LangChain Document | LlamaIndex Node |
|------|---------|---------------------|-------------------|-----------------|
| 层级结构 | 三层 (D-P-E) | 单层（扁平列表） | 单层 | 树形 |
| 页面语义 | 一等公民 | 仅在元数据中 | 无 | 无 |
| 类型安全 | Pydantic 判别联合体 | Python 类继承 | 无 | 弱 |
| 空间信息 | 坐标系 + 转换 | 有坐标系 | 无 | 无 |
| 元数据扩展 | `extra="allow"` | 固定字段集 | 自由 dict | 自由 dict |
| 元素间关系 | parent_id + related_ids | parent_id | 无 | parent/child |
| 表格解析 | 内置行列拆分 | 仅文本 | 无 | 无 |
| 文档间引用 | 双向 citation_uris | 无 | 无 | 无 |
| 数据库映射 | 三表 + GIN 索引 | 无 | 无 | 无 |
| 格式覆盖 | 30+ 种（含代码仓库） | 20+ 种 | 取决于 Loader | 取决于 Reader |

---

## 9. 标准化建议

### 9.1 核心规范

建议将以下内容纳入标准：

1. **三层结构定义**：Document、Page、Element 的必填字段和语义
2. **元素类型枚举**：19 种基础元素类型及其 `category` 标识符
3. **元数据 Schema**：文档级和元素级元数据的标准字段
4. **坐标系规范**：PixelSpace、PointSpace、RelativeCoordinateSystem 及转换算法
5. **序列化格式**：JSON Schema 定义

### 9.2 扩展规范

建议以下内容作为可选扩展：

1. **领域元数据扩展**：通过 `extra="allow"` 机制添加特定行业字段
2. **自定义元素类型**：通过继承机制添加新元素类型的规范
3. **存储映射规范**：关系型数据库、向量数据库、文件系统的映射建议

### 9.3 兼容性

DPE 模型的设计确保了向前兼容和向后兼容：

- **向前兼容**：`extra="allow"` 使得旧版解析器可以安全忽略新版本新增的元数据字段
- **向后兼容**：所有新增字段均设为 `Optional`，新版解析器可以处理旧版数据
- **格式中立**：DPE 不依赖任何特定的序列化格式（JSON、Protobuf、MessagePack 均可），只定义语义结构

---

## 10. 结论

DPE 模型的核心价值在于：它不是又一个文档格式，而是**文档格式之间的通用语言**。

正如 IP 协议不关心底层是以太网还是 Wi-Fi，DPE 模型不关心底层是 PDF 还是 Excel——它提供了一个稳定的、AI 友好的中间表示层，让上层应用可以专注于"理解文档内容"，而不是"解析文档格式"。

我们相信，随着 AI 在文档处理领域的深入应用，一个标准化的文档表示模型将成为基础设施的关键一环。DPE 模型已经在实际工程中证明了它的表达力、扩展性和实用性，具备成为这一标准的基础。

---

## 附录 A: JSON Schema 示例

```json
{
  "doc_id": 1,
  "file_uri": "https://example.com/report.pdf",
  "file_type": "pdf",
  "keywords": ["quarterly", "revenue", "2024"],
  "entrance_page_id": 1,
  "doc_metadata": {
    "created_at": "2024-06-15T10:30:00Z",
    "filename": "report.pdf",
    "languages": ["eng"],
    "summary": "Q2 2024 Revenue Report",
    "forward_citation_uris": [],
    "backward_citation_uris": ["https://example.com/q1-report.pdf"]
  },
  "pages": [
    {
      "page_id": 1,
      "doc_id": 1,
      "number": 0,
      "title": "Cover Page",
      "elements": [
        {
          "ele_id": 1,
          "page_id": 1,
          "text": "Q2 2024 Revenue Report",
          "category": "Title",
          "element_id": "a1b2c3d4e5f6",
          "ele_metadata": {
            "category_depth": 0,
            "languages": ["eng"],
            "coordinates": {
              "points": [[72, 100], [540, 100], [540, 140], [72, 140]],
              "system": {
                "type": "PointSpace",
                "width": 612,
                "height": 792,
                "orientation": "CARTESIAN"
              }
            }
          }
        },
        {
          "ele_id": 2,
          "page_id": 1,
          "text": "Revenue grew 15% year-over-year, driven by strong performance in cloud services.",
          "category": "NarrativeText",
          "element_id": "f6e5d4c3b2a1",
          "ele_metadata": {
            "is_narrative": true,
            "languages": ["eng"]
          }
        }
      ]
    }
  ]
}
```

## 附录 B: 元素类型速查表

| category 值 | 类名 | 典型场景 | 特有字段 |
|-------------|------|----------|----------|
| `UncategorizedText` | TextElement | 无法分类的文本 | — |
| `Title` | Title | 各级标题 | `category_depth` (via metadata) |
| `NarrativeText` | NarrativeText | 正文段落 | — |
| `ListItem` | ListItem | 列表项 | `category_depth` (嵌套深度) |
| `Table` | Table | 完整表格 | `text_as_html`, `header_info` |
| `TableChunk` | TableChunk | 表格行片段 | `header_info` |
| `Image` | Image | 图片 | `image_path`, `image_base64` |
| `CodeSnippet` | CodeSnippet | 代码块 | — |
| `Formula` | Formula | 数学公式 | — |
| `CheckBox` | CheckBoxElement | 复选框 | `checked: bool` |
| `Header` | Header | 页眉 | — |
| `Footer` | Footer | 页脚 | — |
| `PageBreak` | PageBreak | 分页符 | — |
| `PageNumber` | PageNumber | 页码 | — |
| `FigureCaption` | FigureCaption | 图片说明 | — |
| `Address` | Address | 地址信息 | — |
| `EmailAddress` | EmailAddress | 邮件地址 | `sent_from`, `sent_to` |
| `CompositeElement` | CompositeElement | 复合分片 | — |
| `FormKeysValues` | FormKeysValues | 表单键值对 | — |
