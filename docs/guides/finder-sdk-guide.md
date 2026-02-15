# Finder SDK 实现指南

**适用 SDK**: [python-sdk](https://github.com/A2C-SMCP/python-sdk) / [rust-sdk](https://github.com/A2C-SMCP/rust-sdk)

**协议版本**: 0.2.0

!!! info "前置阅读"

    本文档是面向 SDK 开发者的**实现指导**，规范性定义以 `specification/` 目录为准。阅读本文前，请先熟悉以下规范文档：

    - [Finder 文档系统](../specification/finder.md) — DPE 数据模型、URI 协议、Organizer 策略、更新机制
    - [事件定义](../specification/events.md) — 事件常量与路由规则
    - [数据结构](../specification/data-structures.md) — TypedDict 定义（协议数据结构的唯一来源）
    - [错误处理](../specification/error-handling.md) — Finder 错误码 4201-4204

---

## 概述

Finder 是 A2C-SMCP 协议中管理**结构化持久文档**的子系统，它将多个 MCP Server 暴露的 `dpe://` 资源聚合为统一的文档目录视图，支持 Agent 通过**渐进式导航**逐层钻入：目录 → 文档 → 页面 → 元素。

```
┌───────────────────────────────────────────────────┐
│                    Computer                        │
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │MCP Srv A │  │MCP Srv B │  │MCP Srv C │        │
│  │dpe://a   │  │dpe://b   │  │(无文档)   │        │
│  │  /report │  │  /slides │  │          │        │
│  └────┬─────┘  └────┬─────┘  └──────────┘        │
│       │             │                              │
│       ▼             ▼                              │
│  ┌────────────────────────┐                       │
│  │   Finder Organizer     │ ← 过滤、排序、分页    │
│  │   (organize_finder)    │                       │
│  └───────────┬────────────┘                       │
│              │                                     │
└──────────────┼─────────────────────────────────────┘
               │
               ▼
          ┌─────────┐
          │  Agent   │ ← client:get_finder + MCP resources/read
          └─────────┘
```

### 三角色实现权重

| 角色 | 职责 | 工作量 |
|------|------|--------|
| **Server** | 纯路由 — 转发 `client:get_finder`、广播 `notify:update_finder` | 最小 |
| **Computer** | 主要实现方 — Organizer 算法、MCP 资源聚合、变更检测、DPE URI 解析 | **最大** |
| **Agent** | 客户端 — 事件发射、通知处理、渐进式导航辅助方法 | 中等 |

---

## 与 Desktop 实现的关系

!!! tip "核心观点"

    **Finder 与 Desktop 是平行系统，共享相同的三事件模式**（`client:get_*` → `server:update_*` → `notify:update_*`）。已有 Desktop 实现可直接作为模板，"复制 + 改事件名 + 调整业务逻辑" 即可完成大部分工作。

### 模块对照表

| Desktop | Finder | 备注 |
|---------|--------|------|
| `window://` URI 解析 (`utils/window_uri`) | `dpe://` URI 解析 (`utils/dpe_uri`) | 不同 URI 结构，相同模块模式 |
| `desktop/organize.py` | `finder/organize.py` | 不同过滤/排序逻辑，相同接口模式 |
| `GET_DESKTOP_EVENT` | `GET_FINDER_EVENT` | 相同路由机制 |
| `UPDATE_DESKTOP_EVENT` / Notification | `UPDATE_FINDER_EVENT` / Notification | 相同数据结构 `UpdateComputerConfigReq` |
| `ResourceListChangedNotification` (window://) | 同 (dpe://) | 相同检测算法，不同 URI scheme 过滤 |
| `GetDeskTopReq/Ret` | `GetFinderReq/Ret` | Finder 多了 `keywords`、`file_type`、分页 |

### 关键差异

| 维度 | Desktop | Finder |
|------|---------|--------|
| 排序依据 | `priority` 参数（窗口优先级） | `last_modified` 降序 |
| 过滤 | 无 | 关键词过滤 + 文件类型过滤 |
| 分页 | 无（`desktop_size` 限制数量） | `offset` / `limit` 标准分页 |
| 返回值 | `list[str]`（渲染后的字符串） | `list[DPEDocumentSummary]`（结构化文档摘要） |

---

## 事件与数据结构速查

本节以速查表形式列出 SDK 开发者需要实现的全部类型和事件。完整定义请参阅 [数据结构](../specification/data-structures.md) 和 [事件定义](../specification/events.md)。

### 事件常量

=== "Python"

    ```python
    GET_FINDER_EVENT = "client:get_finder"
    UPDATE_FINDER_EVENT = "server:update_finder"
    UPDATE_FINDER_NOTIFICATION = "notify:update_finder"
    ```

=== "Rust"

    ```rust
    pub const GET_FINDER_EVENT: &str = "client:get_finder";
    pub const UPDATE_FINDER_EVENT: &str = "server:update_finder";
    pub const UPDATE_FINDER_NOTIFICATION: &str = "notify:update_finder";
    ```

### 数据结构

=== "Python"

    ```python
    class GetFinderReq(AgentCallData, total=True):
        agent: str                          # Agent 名称
        req_id: str                         # 请求 ID
        computer: str                       # 目标 Computer 名称
        keywords: NotRequired[list[str]]    # 可选：关键词过滤
        file_type: NotRequired[str]         # 可选：文件类型过滤
        offset: NotRequired[int]            # 可选：分页偏移（默认 0）
        limit: NotRequired[int]             # 可选：分页限制（默认 20）

    class GetFinderRet(TypedDict, total=False):
        documents: list[DPEDocumentSummary]  # 文档摘要列表
        total_count: int                     # 总文档数（用于分页）
        req_id: str                          # 请求 ID

    class DPEDocumentSummary(TypedDict):
        doc_ref: str                        # 文档引用键
        uri: str                            # 完整 dpe:// URI
        file_uri: str                       # 原始文件 URI
        file_type: str                      # 文件类型（xlsx, pdf, pptx 等）
        title: str                          # 文档标题
        page_count: int                     # 总页数
        keywords: NotRequired[list[str]]    # 关键词列表
        summary: NotRequired[str]           # 文档摘要
        server: str                         # 来源 MCP Server 名称
        last_modified: NotRequired[str]     # 最后修改时间（ISO 8601）

    class DPEPageSummary(TypedDict):
        page_index: int                     # 页码（从 0 开始）
        title: str                          # 页面标题
        element_count: int                  # 元素数量
        uri: str                            # 页面的 dpe:// URI
        doc_ref: NotRequired[str]           # 所属文档引用键

    class DPEElementDetail(TypedDict):
        element_id: str                     # 元素唯一标识
        category: str                       # 元素类型
        summary: NotRequired[str]           # 元素摘要
        content: dict                       # 元素内容
        doc_ref: NotRequired[str]           # 所属文档引用键
        page_index: NotRequired[int]        # 所属页码
        uri: NotRequired[str]              # 元素的 dpe:// URI
        metadata: NotRequired[dict]         # 附加元数据

    class UpdateComputerConfigReq(TypedDict):
        computer: str                       # Computer 名称（复用 Desktop 已有结构）
    ```

=== "Rust"

    ```rust
    #[derive(Debug, Serialize, Deserialize)]
    pub struct GetFinderReq {
        pub agent: String,
        pub req_id: String,
        pub computer: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub keywords: Option<Vec<String>>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub file_type: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub offset: Option<i64>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub limit: Option<i64>,
    }

    #[derive(Debug, Serialize, Deserialize)]
    pub struct GetFinderRet {
        pub documents: Vec<DPEDocumentSummary>,
        pub total_count: i64,
        pub req_id: String,
    }

    #[derive(Debug, Serialize, Deserialize)]
    pub struct DPEDocumentSummary {
        pub doc_ref: String,
        pub uri: String,
        pub file_uri: String,
        pub file_type: String,
        pub title: String,
        pub page_count: i64,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub keywords: Option<Vec<String>>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub summary: Option<String>,
        pub server: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub last_modified: Option<String>,
    }

    #[derive(Debug, Serialize, Deserialize)]
    pub struct DPEPageSummary {
        pub page_index: i64,
        pub title: String,
        pub element_count: i64,
        pub uri: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub doc_ref: Option<String>,
    }

    #[derive(Debug, Serialize, Deserialize)]
    pub struct DPEElementDetail {
        pub element_id: String,
        pub category: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub summary: Option<String>,
        pub content: serde_json::Value,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub doc_ref: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub page_index: Option<i64>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub uri: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub metadata: Option<serde_json::Value>,
    }

    // 复用 Desktop 已有结构
    #[derive(Debug, Serialize, Deserialize)]
    pub struct UpdateComputerConfigReq {
        pub computer: String,
    }
    ```

### 错误码

| 代码 | 名称 | 含义 |
|------|------|------|
| 4201 | Document Not Found | 文档引用（`doc_ref`）不存在 |
| 4202 | Page Out of Range | 页码超出文档的 `page_count` 范围 |
| 4203 | Element Not Found | 元素 ID 不存在 |
| 4204 | Invalid DPE URI | `dpe://` URI 格式错误或校验失败 |

---

## Server 实现（最小工作量）

Server 对 Finder 的处理与 Desktop **完全对称**，仅事件名不同。如果 Desktop 的对应处理器已工作，Finder 只需复制并改事件名。

### 需修改文件

| SDK | 文件 |
|-----|------|
| Python | `server/namespace.py` + `server/sync_namespace.py` |
| Rust | `src/server/handlers.rs` |

### 事件处理器 1：`client:get_finder` 路由

与 `client:get_desktop` 相同模式 — 从请求中提取 `computer`，查 `name_to_sid`，转发到目标 Computer，返回结果。

=== "Python"

    ```python
    # server/namespace.py — 对照 client:get_desktop 处理器

    @self.on(GET_FINDER_EVENT)
    async def handle_get_finder(sid, data: GetFinderReq):
        computer_name = data["computer"]
        computer_sid = self.name_to_sid.get(computer_name)
        if not computer_sid:
            return {"error": {"code": 404, "message": f"Computer '{computer_name}' not found"}}

        result = await self.emit(
            GET_FINDER_EVENT,
            data,
            to=computer_sid,
        )
        return result
    ```

=== "Rust"

    ```rust
    // src/server/handlers.rs — 对照 client:get_desktop 处理器

    async fn handle_get_finder(
        &self,
        sid: Sid,
        data: GetFinderReq,
    ) -> Result<GetFinderRet, SmcpError> {
        let computer_sid = self.name_to_sid
            .get(&data.computer)
            .ok_or_else(|| SmcpError::not_found(
                format!("Computer '{}' not found", data.computer)
            ))?;

        self.emit(GET_FINDER_EVENT, &data, *computer_sid).await
    }
    ```

### 事件处理器 2：`server:update_finder` 广播

收到 `UpdateComputerConfigReq`，广播 `notify:update_finder` 到房间。

=== "Python"

    ```python
    # server/namespace.py — 对照 server:update_desktop 处理器

    @self.on(UPDATE_FINDER_EVENT)
    async def handle_update_finder(sid, data: UpdateComputerConfigReq):
        room = self.sid_to_room.get(sid)
        if room:
            await self.emit(
                UPDATE_FINDER_NOTIFICATION,
                data,
                room=room,
                skip_sid=sid,
            )
    ```

=== "Rust"

    ```rust
    // src/server/handlers.rs — 对照 server:update_desktop 处理器

    async fn handle_update_finder(
        &self,
        sid: Sid,
        data: UpdateComputerConfigReq,
    ) -> Result<(), SmcpError> {
        if let Some(room) = self.sid_to_room.get(&sid) {
            self.broadcast(
                UPDATE_FINDER_NOTIFICATION,
                &data,
                room,
                Some(sid), // skip_sid
            ).await?;
        }
        Ok(())
    }
    ```

---

## Computer 实现（主要工作）

Computer 是 Finder 功能的核心实现方，负责 DPE URI 解析、MCP 资源聚合、Organizer 排序和变更检测。

### 推荐模块结构

```
computer/
├── finder/
│   ├── organize.py      # organize_finder() 算法
│   └── aggregator.py    # MCP 资源聚合 + 变更检测
├── utils/
│   └── dpe_uri.py       # DPE URI 解析器
```

此结构与 Desktop 的 `desktop/organize.py` + `utils/window_uri.py` 镜像。

### DPE URI 解析器

#### 接口定义

=== "Python"

    ```python
    # computer/utils/dpe_uri.py

    from dataclasses import dataclass
    from typing import Optional

    @dataclass
    class ParsedDPEUri:
        scheme: str                          # 固定 "dpe"
        host: str                            # MCP Server 标识
        doc_ref: Optional[str]               # 文档引用键
        sub_path: Optional[str]              # "pages/{N}" 或 "elements/{ID}"
        query_params: dict[str, str]         # format, depth, offset, limit, categories

        @property
        def level(self) -> int:
            """返回 URI 级别：0=目录, 1=文档, 2=页面, 3=元素"""
            if self.doc_ref is None:
                return 0
            if self.sub_path is None:
                return 1
            if self.sub_path.startswith("pages/"):
                return 2
            if self.sub_path.startswith("elements/"):
                return 3
            return -1  # 无效


    def parse_dpe_uri(raw: str) -> ParsedDPEUri:
        """解析 dpe:// URI，校验失败抛出 ValueError（错误码 4204）"""
        ...


    def build_dpe_uri(
        host: str,
        doc_ref: Optional[str] = None,
        sub_path: Optional[str] = None,
        params: Optional[dict[str, str]] = None,
    ) -> str:
        """构造 dpe:// URI"""
        ...
    ```

=== "Rust"

    ```rust
    // computer/utils/dpe_uri.rs

    #[derive(Debug, Clone)]
    pub struct ParsedDPEUri {
        pub scheme: String,                      // 固定 "dpe"
        pub host: String,                        // MCP Server 标识
        pub doc_ref: Option<String>,             // 文档引用键
        pub sub_path: Option<String>,            // "pages/{N}" 或 "elements/{ID}"
        pub query_params: HashMap<String, String>,
    }

    impl ParsedDPEUri {
        /// 返回 URI 级别：0=目录, 1=文档, 2=页面, 3=元素
        pub fn level(&self) -> i32 {
            match (&self.doc_ref, &self.sub_path) {
                (None, _) => 0,
                (Some(_), None) => 1,
                (Some(_), Some(sp)) if sp.starts_with("pages/") => 2,
                (Some(_), Some(sp)) if sp.starts_with("elements/") => 3,
                _ => -1,
            }
        }
    }

    pub fn parse_dpe_uri(raw: &str) -> Result<ParsedDPEUri, SmcpError> { ... }

    pub fn build_dpe_uri(
        host: &str,
        doc_ref: Option<&str>,
        sub_path: Option<&str>,
        params: Option<&HashMap<String, String>>,
    ) -> String { ... }
    ```

#### 8 条校验规则

解析器必须按以下规则校验输入 URI，任一规则失败应返回错误码 **4204**（Invalid DPE URI）：

1. `scheme` 必须为 `dpe`
2. `host` 不能为空
3. `sub-path` 若存在，必须匹配 `pages/{非负整数}` 或 `elements/{非空字符串}`
4. `format` 若存在，必须为 `json`、`markdown`、`text` 之一
5. `depth` 若存在，必须为 `metadata` 或 `pages`
6. `offset` 若存在，必须为非负整数
7. `limit` 若存在，必须为 `[1, 100]` 范围内的整数
8. `categories` 若存在，必须是合法的 [元素类型](../specification/finder.md#元素类型) 的逗号分隔列表

### Finder Organizer 算法

#### 完整伪代码

```python
def organize_finder(
    documents: list[DPEDocumentSummary],
    keywords: list[str] | None,
    file_type: str | None,
    history: list[str],           # 工具调用历史中的 MCP Server 名称列表
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[DPEDocumentSummary], int]:
    """
    返回 (分页后的文档列表, 过滤后的总文档数 total_count)
    """

    # Step 1: 过滤无效 URI 文档
    docs = [d for d in documents if is_valid_dpe_uri(d["uri"])]

    # Step 2: 关键词过滤（OR 匹配 title / keywords / summary）
    if keywords:
        docs = [
            d for d in docs
            if any(
                kw.lower() in d["title"].lower()
                or kw.lower() in " ".join(d.get("keywords", [])).lower()
                or kw.lower() in d.get("summary", "").lower()
                for kw in keywords
            )
        ]

    # Step 3: 文件类型过滤（精确匹配）
    if file_type:
        docs = [d for d in docs if d["file_type"] == file_type]

    # Step 4: Server 优先级排序
    # 反向遍历工具调用历史，去重，得到最近使用的 Server 列表
    seen = set()
    server_order = []
    for server_name in reversed(history):
        if server_name not in seen:
            seen.add(server_name)
            server_order.append(server_name)
    # 未出现在历史中的 Server 按名称字母序追加
    remaining = sorted(set(d["server"] for d in docs) - seen)
    server_order.extend(remaining)
    server_rank = {name: i for i, name in enumerate(server_order)}

    # Step 5: Server 内按 last_modified 降序
    def sort_key(d):
        rank = server_rank.get(d["server"], len(server_order))
        lm = d.get("last_modified", "")
        return (rank, "" if lm else "z", lm and (-1,) or (0,))
        # 简化：实际实现中使用 ISO 8601 时间戳倒序

    docs.sort(key=lambda d: (
        server_rank.get(d["server"], len(server_order)),
        d.get("last_modified") is None,       # None 排末尾
        "" if d.get("last_modified") is None
           else d["last_modified"],
    ), reverse=False)
    # 注意：last_modified 降序需要额外处理（反转非 None 值排序）

    # Step 6: 分页
    total_count = len(docs)
    paginated = docs[offset : offset + limit]

    return paginated, total_count
```

!!! warning "与 Desktop Organizer 的差异"

    | 差异点 | Desktop | Finder |
    |--------|---------|--------|
    | 排序依据 | `priority` 参数（窗口优先级） | `last_modified` 降序 |
    | 关键词过滤 | 无 | `keywords` 参数，OR 匹配 title/keywords/summary |
    | 文件类型过滤 | 无 | `file_type` 参数，精确匹配 |
    | 分页 | `desktop_size` 截断 | `offset`/`limit` 标准分页 + `total_count` |

#### 实现示例

=== "Python"

    ```python
    # computer/finder/organize.py

    from typing import Optional

    def organize_finder(
        documents: list[dict],
        keywords: Optional[list[str]] = None,
        file_type: Optional[str] = None,
        history: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        history = history or []

        # Step 1: 过滤无效文档
        docs = [d for d in documents if d.get("uri", "").startswith("dpe://")]

        # Step 2: 关键词过滤
        if keywords:
            def matches_keywords(doc: dict) -> bool:
                searchable = (
                    doc.get("title", "").lower()
                    + " " + " ".join(doc.get("keywords", [])).lower()
                    + " " + doc.get("summary", "").lower()
                )
                return any(kw.lower() in searchable for kw in keywords)
            docs = [d for d in docs if matches_keywords(d)]

        # Step 3: 文件类型过滤
        if file_type:
            docs = [d for d in docs if d.get("file_type") == file_type]

        # Step 4: 构建 Server 优先级
        seen: set[str] = set()
        server_order: list[str] = []
        for name in reversed(history):
            if name not in seen:
                seen.add(name)
                server_order.append(name)
        remaining = sorted(set(d["server"] for d in docs) - seen)
        server_order.extend(remaining)
        rank = {name: i for i, name in enumerate(server_order)}

        # Step 5: 排序（Server 优先级升序，last_modified 降序）
        docs.sort(key=lambda d: (
            rank.get(d["server"], len(server_order)),
            0 if d.get("last_modified") else 1,
            "" if not d.get("last_modified") else
                chr(0) + str(-ord(c) for c in d["last_modified"]),
        ))
        # 实际实现建议：按 (server_rank, -timestamp) 排序

        # Step 6: 分页
        total_count = len(docs)
        return docs[offset:offset + limit], total_count
    ```

=== "Rust"

    ```rust
    // computer/finder/organize.rs

    pub fn organize_finder(
        documents: Vec<DPEDocumentSummary>,
        keywords: Option<&[String]>,
        file_type: Option<&str>,
        history: &[String],
        offset: usize,
        limit: usize,
    ) -> (Vec<DPEDocumentSummary>, usize) {
        // Step 1: 过滤无效文档
        let mut docs: Vec<_> = documents.into_iter()
            .filter(|d| d.uri.starts_with("dpe://"))
            .collect();

        // Step 2: 关键词过滤
        if let Some(kws) = keywords {
            docs.retain(|d| {
                let searchable = format!(
                    "{} {} {}",
                    d.title.to_lowercase(),
                    d.keywords.as_deref().unwrap_or(&[]).join(" ").to_lowercase(),
                    d.summary.as_deref().unwrap_or("").to_lowercase(),
                );
                kws.iter().any(|kw| searchable.contains(&kw.to_lowercase()))
            });
        }

        // Step 3: 文件类型过滤
        if let Some(ft) = file_type {
            docs.retain(|d| d.file_type == ft);
        }

        // Step 4: 构建 Server 优先级
        let mut seen = HashSet::new();
        let mut server_order = Vec::new();
        for name in history.iter().rev() {
            if seen.insert(name.clone()) {
                server_order.push(name.clone());
            }
        }
        let mut remaining: Vec<_> = docs.iter()
            .map(|d| d.server.clone())
            .collect::<HashSet<_>>()
            .difference(&seen)
            .cloned()
            .collect();
        remaining.sort();
        server_order.extend(remaining);
        let rank: HashMap<_, _> = server_order.iter()
            .enumerate()
            .map(|(i, n)| (n.clone(), i))
            .collect();

        // Step 5: 排序
        docs.sort_by(|a, b| {
            let ra = rank.get(&a.server).copied().unwrap_or(usize::MAX);
            let rb = rank.get(&b.server).copied().unwrap_or(usize::MAX);
            ra.cmp(&rb).then_with(|| {
                // last_modified 降序（None 排末尾）
                match (&b.last_modified, &a.last_modified) {
                    (Some(b_lm), Some(a_lm)) => b_lm.cmp(a_lm),
                    (Some(_), None) => std::cmp::Ordering::Less,
                    (None, Some(_)) => std::cmp::Ordering::Greater,
                    (None, None) => std::cmp::Ordering::Equal,
                }
            })
        });

        // Step 6: 分页
        let total_count = docs.len();
        let paginated = docs.into_iter()
            .skip(offset)
            .take(limit)
            .collect();

        (paginated, total_count)
    }
    ```

### MCP 资源聚合

Computer 启动后，需要从所有 MCP Server 收集 `dpe://` 资源：

1. **枚举** — 遍历所有声明 `resources.subscribe` 能力的 MCP Server
2. **收集** — 调用每个 Server 的 `resources/list`，过滤出 `dpe://` URI
3. **构建** — 读取 Level 1 元数据，构建 `DPEDocumentSummary` 列表
4. **缓存** — 维护 URI 缓存集合（用于后续变更检测）

=== "Python"

    ```python
    # computer/finder/aggregator.py

    class FinderAggregator:
        def __init__(self, mcp_clients: dict[str, MCPClient]):
            self._clients = mcp_clients
            self._uri_cache: set[str] = set()

        async def collect_documents(self) -> list[DPEDocumentSummary]:
            """从所有 MCP Server 收集 dpe:// 文档摘要"""
            documents = []
            for server_name, client in self._clients.items():
                if not client.has_capability("resources.subscribe"):
                    continue
                resources = await client.list_resources()
                for res in resources:
                    if not res.uri.startswith("dpe://"):
                        continue
                    # 读取 Level 1 元数据
                    metadata = await client.read_resource(res.uri)
                    doc = self._build_summary(metadata, server_name)
                    documents.append(doc)
            return documents

        def update_uri_cache(self, current_uris: set[str]) -> bool:
            """更新缓存，返回是否有变化"""
            changed = current_uris != self._uri_cache
            self._uri_cache = current_uris.copy()
            return changed
    ```

=== "Rust"

    ```rust
    // computer/finder/aggregator.rs

    pub struct FinderAggregator {
        clients: HashMap<String, McpClient>,
        uri_cache: HashSet<String>,
    }

    impl FinderAggregator {
        pub async fn collect_documents(&self) -> Result<Vec<DPEDocumentSummary>> {
            let mut documents = Vec::new();
            for (server_name, client) in &self.clients {
                if !client.has_capability("resources.subscribe") {
                    continue;
                }
                let resources = client.list_resources().await?;
                for res in resources {
                    if !res.uri.starts_with("dpe://") {
                        continue;
                    }
                    let metadata = client.read_resource(&res.uri).await?;
                    let doc = self.build_summary(metadata, server_name);
                    documents.push(doc);
                }
            }
            Ok(documents)
        }

        pub fn update_uri_cache(&mut self, current_uris: HashSet<String>) -> bool {
            let changed = current_uris != self.uri_cache;
            self.uri_cache = current_uris;
            changed
        }
    }
    ```

### 变更检测

Computer 监听两种 MCP 通知来检测文档变化（与 Desktop 的 `window://` 检测逻辑对称）：

#### ResourceListChangedNotification

```
MCP Server 发出 ResourceListChangedNotification
    → Computer 收集当前所有 dpe:// URI
    → 与缓存的 URI 集合比较
    → 集合不同 → emit server:update_finder
    → 集合相同 → 跳过（仅记录日志）
```

=== "Python"

    ```python
    async def on_resource_list_changed(self, server_name: str):
        """处理 ResourceListChangedNotification"""
        resources = await self._clients[server_name].list_resources()
        current_uris = {
            r.uri for r in resources if r.uri.startswith("dpe://")
        }
        if self._aggregator.update_uri_cache(current_uris):
            await self._sio.emit(UPDATE_FINDER_EVENT, {
                "computer": self._name
            })
    ```

=== "Rust"

    ```rust
    async fn on_resource_list_changed(&mut self, server_name: &str) -> Result<()> {
        let resources = self.clients[server_name].list_resources().await?;
        let current_uris: HashSet<String> = resources.iter()
            .filter(|r| r.uri.starts_with("dpe://"))
            .map(|r| r.uri.clone())
            .collect();

        if self.aggregator.update_uri_cache(current_uris) {
            self.sio.emit(UPDATE_FINDER_EVENT, &UpdateComputerConfigReq {
                computer: self.name.clone(),
            }).await?;
        }
        Ok(())
    }
    ```

#### ResourceUpdatedNotification

```
MCP Server 发出 ResourceUpdatedNotification（携带具体 URI）
    → Computer 检查该 URI 是否为 dpe://
    → 是 → 直接 emit server:update_finder（无需集合比较，降低延迟）
    → 否 → 忽略
```

=== "Python"

    ```python
    async def on_resource_updated(self, uri: str):
        """处理 ResourceUpdatedNotification"""
        if uri.startswith("dpe://"):
            await self._sio.emit(UPDATE_FINDER_EVENT, {
                "computer": self._name
            })
    ```

=== "Rust"

    ```rust
    async fn on_resource_updated(&mut self, uri: &str) -> Result<()> {
        if uri.starts_with("dpe://") {
            self.sio.emit(UPDATE_FINDER_EVENT, &UpdateComputerConfigReq {
                computer: self.name.clone(),
            }).await?;
        }
        Ok(())
    }
    ```

### `client:get_finder` 事件处理器

=== "Python"

    ```python
    @self.on(GET_FINDER_EVENT)
    async def handle_get_finder(sid, data: GetFinderReq):
        # 1. 收集文档
        documents = await self._aggregator.collect_documents()

        # 2. 组织（过滤 + 排序 + 分页）
        paginated, total_count = organize_finder(
            documents=documents,
            keywords=data.get("keywords"),
            file_type=data.get("file_type"),
            history=self._tool_call_history,
            offset=data.get("offset", 0),
            limit=data.get("limit", 20),
        )

        # 3. 返回结果
        return GetFinderRet(
            documents=paginated,
            total_count=total_count,
            req_id=data["req_id"],
        )
    ```

=== "Rust"

    ```rust
    async fn handle_get_finder(&self, data: GetFinderReq) -> Result<GetFinderRet> {
        // 1. 收集文档
        let documents = self.aggregator.collect_documents().await?;

        // 2. 组织
        let (paginated, total_count) = organize_finder(
            documents,
            data.keywords.as_deref(),
            data.file_type.as_deref(),
            &self.tool_call_history,
            data.offset.unwrap_or(0) as usize,
            data.limit.unwrap_or(20) as usize,
        );

        // 3. 返回结果
        Ok(GetFinderRet {
            documents: paginated,
            total_count: total_count as i64,
            req_id: data.req_id,
        })
    }
    ```

### `resources/read` 桥接

当 Agent 通过标准 MCP `resources/read` 请求 `dpe://` 资源时，Computer 需要将请求桥接到正确的 MCP Server：

1. 解析 `dpe://` URI 中的 `host`
2. 根据 `host` 查找对应的 MCP Server
3. 转发 `resources/read` 请求
4. 返回 MCP Server 的响应

```python
async def read_resource(self, uri: str):
    parsed = parse_dpe_uri(uri)
    client = self._find_client_by_host(parsed.host)
    if not client:
        raise SmcpError(4201, f"No MCP Server found for host: {parsed.host}")
    return await client.read_resource(uri)
```

---

## Agent 实现（客户端）

### 需修改文件

| SDK | 文件 |
|-----|------|
| Python | `agent/client.py` + `agent/sync_client.py` + `agent/types.py` |
| Rust | `src/agent/client.rs` + `src/agent/types.rs` |

### `get_finder()` 方法

=== "Python"

    ```python
    # agent/client.py

    async def get_finder(
        self,
        computer: str,
        keywords: list[str] | None = None,
        file_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> GetFinderRet:
        """获取指定 Computer 的文档目录"""
        req: GetFinderReq = {
            "agent": self._name,
            "req_id": self._gen_req_id(),
            "computer": computer,
        }
        if keywords is not None:
            req["keywords"] = keywords
        if file_type is not None:
            req["file_type"] = file_type
        if offset != 0:
            req["offset"] = offset
        if limit != 20:
            req["limit"] = limit

        result = await self._sio.emit(
            GET_FINDER_EVENT,
            req,
            callback=True,
        )
        return result
    ```

=== "Rust"

    ```rust
    // src/agent/client.rs

    pub async fn get_finder(
        &self,
        computer: &str,
        keywords: Option<Vec<String>>,
        file_type: Option<String>,
        offset: Option<i64>,
        limit: Option<i64>,
    ) -> Result<GetFinderRet> {
        let req = GetFinderReq {
            agent: self.name.clone(),
            req_id: self.gen_req_id(),
            computer: computer.to_string(),
            keywords,
            file_type,
            offset,
            limit,
        };

        self.sio.emit(GET_FINDER_EVENT, &req).await
    }
    ```

### 通知处理器

注册 `notify:update_finder` 监听器，推荐收到通知后自动调用 `get_finder()` 刷新文档目录。

=== "Python"

    ```python
    # agent/client.py

    @self._sio.on(UPDATE_FINDER_NOTIFICATION)
    async def on_finder_updated(data: UpdateComputerConfigReq):
        computer = data["computer"]
        # 推荐：自动刷新文档目录
        new_finder = await self.get_finder(computer=computer)
        self._on_finder_changed(computer, new_finder)
    ```

=== "Rust"

    ```rust
    // src/agent/client.rs

    self.sio.on(UPDATE_FINDER_NOTIFICATION, |data: UpdateComputerConfigReq| {
        let computer = data.computer.clone();
        // 推荐：自动刷新文档目录
        let new_finder = self.get_finder(&computer, None, None, None, None).await?;
        self.on_finder_changed(&computer, new_finder);
    });
    ```

### 渐进式导航辅助方法（可选）

以下便利方法封装 `resources/read`，简化 Agent 对 DPE 文档的逐层导航。这些是 **SDK 便利封装，非协议必须**。

=== "Python"

    ```python
    # agent/client.py — 可选便利方法

    async def read_document_metadata(
        self, computer: str, uri: str
    ) -> dict:
        """Level 1: 读取文档元数据"""
        return await self.read_resource(computer=computer, uri=uri)

    async def read_document_pages(
        self, computer: str, uri: str, offset: int = 0, limit: int = 20
    ) -> dict:
        """Level 1 + depth=pages: 读取文档元数据和页面索引"""
        paged_uri = f"{uri}?depth=pages&offset={offset}&limit={limit}"
        return await self.read_resource(computer=computer, uri=paged_uri)

    async def read_page(
        self, computer: str, uri: str, page_index: int, format: str = "json"
    ) -> dict:
        """Level 2: 读取指定页面内容"""
        page_uri = f"{uri}/pages/{page_index}?format={format}"
        return await self.read_resource(computer=computer, uri=page_uri)

    async def read_element(
        self, computer: str, uri: str, element_id: str
    ) -> dict:
        """Level 3: 读取指定元素详情"""
        elem_uri = f"{uri}/elements/{element_id}"
        return await self.read_resource(computer=computer, uri=elem_uri)
    ```

=== "Rust"

    ```rust
    // src/agent/client.rs — 可选便利方法

    /// Level 1: 读取文档元数据
    pub async fn read_document_metadata(
        &self, computer: &str, uri: &str,
    ) -> Result<serde_json::Value> {
        self.read_resource(computer, uri).await
    }

    /// Level 1 + depth=pages: 读取文档元数据和页面索引
    pub async fn read_document_pages(
        &self, computer: &str, uri: &str, offset: i64, limit: i64,
    ) -> Result<serde_json::Value> {
        let paged_uri = format!("{uri}?depth=pages&offset={offset}&limit={limit}");
        self.read_resource(computer, &paged_uri).await
    }

    /// Level 2: 读取指定页面内容
    pub async fn read_page(
        &self, computer: &str, uri: &str, page_index: i64, format: &str,
    ) -> Result<serde_json::Value> {
        let page_uri = format!("{uri}/pages/{page_index}?format={format}");
        self.read_resource(computer, &page_uri).await
    }

    /// Level 3: 读取指定元素详情
    pub async fn read_element(
        &self, computer: &str, uri: &str, element_id: &str,
    ) -> Result<serde_json::Value> {
        let elem_uri = format!("{uri}/elements/{element_id}");
        self.read_resource(computer, &elem_uri).await
    }
    ```

---

## 错误处理

### 错误码详解

| 代码 | 名称 | 触发场景 | 产生角色 | 传播路径 |
|------|------|---------|---------|---------|
| **4201** | Document Not Found | `resources/read` 时 `doc_ref` 不存在 | MCP Server | MCP Server → Computer → Server → Agent |
| **4202** | Page Out of Range | `resources/read` 时 `page_index >= page_count` | MCP Server | MCP Server → Computer → Server → Agent |
| **4203** | Element Not Found | `resources/read` 时 `element_id` 不存在 | MCP Server | MCP Server → Computer → Server → Agent |
| **4204** | Invalid DPE URI | URI 格式错误或校验规则不通过 | Computer | Computer → Server → Agent |

### 错误构造示例

=== "Python"

    ```python
    # 错误响应构造
    def make_finder_error(code: int, message: str, details: dict | None = None) -> dict:
        error = {"error": {"code": code, "message": message}}
        if details:
            error["error"]["details"] = details
        return error

    # 使用示例
    make_finder_error(4201, "Document not found", {"doc_ref": "nonexistent"})
    make_finder_error(4202, "Page out of range", {"page_index": 99, "page_count": 12})
    make_finder_error(4203, "Element not found", {"element_id": "bad-id"})
    make_finder_error(4204, "Invalid DPE URI", {"uri": "invalid://..."})
    ```

=== "Rust"

    ```rust
    // 错误枚举
    #[derive(Debug, thiserror::Error)]
    pub enum FinderError {
        #[error("Document not found: {doc_ref}")]
        DocumentNotFound { doc_ref: String },

        #[error("Page {page_index} out of range (page_count: {page_count})")]
        PageOutOfRange { page_index: i64, page_count: i64 },

        #[error("Element not found: {element_id}")]
        ElementNotFound { element_id: String },

        #[error("Invalid DPE URI: {uri}")]
        InvalidDPEUri { uri: String },
    }

    impl FinderError {
        pub fn code(&self) -> i32 {
            match self {
                Self::DocumentNotFound { .. } => 4201,
                Self::PageOutOfRange { .. } => 4202,
                Self::ElementNotFound { .. } => 4203,
                Self::InvalidDPEUri { .. } => 4204,
            }
        }
    }
    ```

### 传播链

```
MCP Server                Computer              Server              Agent
    │                         │                    │                   │
    │  4201/4202/4203         │                    │                   │
    ├────────────────────────►│                    │                   │
    │  (resources/read 失败)  │  包装为标准错误响应  │                   │
    │                         ├───────────────────►│                   │
    │                         │                    │  透传错误响应       │
    │                         │                    ├──────────────────►│
    │                         │                    │                   │
    │                         │  4204              │                   │
    │                         │  (URI 解析失败)     │                   │
    │                         ├───────────────────►│                   │
    │                         │                    ├──────────────────►│
```

每一层应：

1. **记录错误日志**（含 `req_id` 便于追踪）
2. **向上传播错误**（不丢失原始错误细节）
3. **不暴露敏感信息**（如内部 IP、凭证）

---

## 测试策略

### 单元测试

#### DPE URI 解析器

- 8 条校验规则覆盖（每条规则至少一个正例 + 一个反例）
- 四级 URI 解析（Level 0 ~ Level 3）
- 查询参数组合（format / depth / offset / limit / categories）
- 边界情况：空字符串、仅 scheme、特殊字符编码

#### Finder Organizer

- 空输入 → 返回空列表 + `total_count = 0`
- 关键词匹配 → 分别匹配 `title`、`keywords`、`summary`
- 文件类型过滤 → 精确匹配、不匹配时返回空
- Server 优先级 → 最近使用的 Server 排在前面
- `last_modified` 排序 → 降序、缺失值排末尾
- 分页边界 → `offset` 超出范围、`limit = 0`、`limit > total`
- `total_count` → 反映过滤后的总数，而非分页后的数量

#### 变更检测

- URI 集合相同 → 不触发更新
- URI 集合不同（新增/删除） → 触发更新
- `dpe://` vs 非 `dpe://` URI → 仅关注 `dpe://`

### 集成测试

#### 完整 Finder 流程

```
Mock MCP Server → Computer 聚合 → Server 路由 → Agent 接收
```

- Agent 发送 `client:get_finder` → 收到正确的 `GetFinderRet`
- 带 `keywords` / `file_type` / `offset` / `limit` 参数的过滤请求

#### 更新通知链

```
MCP 通知 → Computer 检测 → Server 广播 → Agent 刷新
```

- `ResourceListChangedNotification` → Computer 检测 → `server:update_finder` → Agent 收到 `notify:update_finder`
- `ResourceUpdatedNotification`（`dpe://` URI） → 同上

#### 渐进式导航

- Level 0 → Level 1 → Level 2 → Level 3 逐级读取
- 带查询参数的读取（`depth=pages`、`format=markdown`、`categories=table`）

#### 错误传播

- 无效 `doc_ref` → 4201 错误正确传递到 Agent
- 无效 URI → 4204 错误由 Computer 产生
- 页码超范围 → 4202 错误

### Desktop 对照

测试文件结构应与 Desktop 测试镜像，便于维护和对比：

| Desktop 测试 | Finder 测试 |
|-------------|-------------|
| `test_window_uri.py` | `test_dpe_uri.py` |
| `test_organize_desktop.py` | `test_organize_finder.py` |
| `test_desktop_update.py` | `test_finder_update.py` |
| `test_desktop_e2e.py` | `test_finder_e2e.py` |

---

## 实现清单

### Server

- [ ] **注册 `client:get_finder` 事件处理器** — 路由转发（小）
- [ ] **注册 `server:update_finder` 事件处理器** — 广播通知（小）
- [ ] **同步版本** — `sync_namespace.py` 对应处理器（小）

### Computer

- [ ] **DPE URI 解析器** — `utils/dpe_uri.py`，含 8 条校验规则（中）
- [ ] **Finder Organizer** — `finder/organize.py`，含过滤 + 排序 + 分页（中）
- [ ] **MCP 资源聚合器** — `finder/aggregator.py`，枚举 + 收集 + 缓存（中）
- [ ] **变更检测** — `ResourceListChanged` + `ResourceUpdated` 处理（中）
- [ ] **`client:get_finder` 事件处理器** — 收集 → 组织 → 返回（小）
- [ ] **`resources/read` 桥接** — URI 解析 → 路由到正确的 MCP Server（小）
- [ ] **DPE URI 解析器单元测试**（中）
- [ ] **Finder Organizer 单元测试**（中）
- [ ] **变更检测单元测试**（小）

### Agent

- [ ] **`get_finder()` 方法** — 构造请求 + emit + 返回（小）
- [ ] **同步版本** — `sync_client.py` 对应方法（小）
- [ ] **`notify:update_finder` 通知处理器**（小）
- [ ] **渐进式导航辅助方法（可选）** — 4 个便利方法（中）
- [ ] **类型定义** — `agent/types.py` 中添加 Finder 相关类型（小）
- [ ] **集成测试** — 完整 Finder 流程 + 更新通知链（大）
