# A2C-SMCP 数据结构定义

本文档定义了 A2C-SMCP 协议的所有数据结构，基于 `a2c_smcp/smcp.py` 中的 TypedDict 定义。

## 通用约定

- 所有数据结构使用 JSON 对象表示
- 字段命名使用 `snake_case` 风格
- 可选字段使用 `NotRequired` 标注
- 时间相关字段：超时使用整数秒

---

## 基础数据结构

### AgentCallData

Agent 发起调用的基础数据，被多个请求结构继承。

```python
class AgentCallData(TypedDict):
    agent: str      # Agent 名称/标识
    req_id: str     # 请求 ID，用于去重和关联
```

> **取消事件复用本结构**：`server:tool_call_cancel` / `notify:tool_call_cancel` 直接复用 `AgentCallData`，其中 `req_id` **MUST** 等于被取消的原 `client:tool_call` 的 `req_id`（唯一定位在途调用），且**不含** `computer` 字段。详见 [事件 §server:tool_call_cancel](events.md#servertool_call_cancel)。

---

## 工具相关结构

### ToolCallReq

工具调用请求，继承自 `AgentCallData`。

```python
class ToolCallReq(AgentCallData):
    agent: str          # Agent 名称
    req_id: str         # 请求 ID
    computer: str       # 目标 Computer 名称
    tool_name: str      # 工具名称
    params: dict        # 工具调用参数
    timeout: int        # 超时时间（秒）
```

### SMCPTool

SMCP 协议中的工具定义，用于工具列表返回。

```python
class SMCPTool(TypedDict):
    name: str                           # 工具名称
    description: str                    # 工具描述
    params_schema: dict                 # 参数 JSON Schema
    return_schema: dict | None          # 返回值 JSON Schema（可选）
    meta: NotRequired[Attributes | None]  # 工具元数据（可选）
```

**说明**: `name` 承载的是**聚合后的 `exposed_tool_name`**（`{bundle_id}__{alias ?? 原始工具名}`），跨 Server / marketplace / plugin 保证唯一。命名生成、去重与路由规则见 [MCP Tool 命名与路由（BundleID 模型）](#mcp-tool-命名与路由)。

### SMCPTool.meta 序列化规范 { #smcptoolmeta-序列化规范 }

`SMCPTool.meta` 是工具的元数据字段，类型为 `Attributes = Mapping[str, AttributeValue]`。由于 `AttributeValue` 仅支持简单类型（`str | bool | int | float | Sequence[str]` 等），**所有复杂结构必须序列化为 JSON 字符串后存入**。

#### meta 的命名空间结构

`meta` 是一个多方写入的字段，不同来源的数据通过**命名空间 key** 隔离：

| Key | 写入方 | 说明 |
|-----|-------|------|
| `a2c_tool_meta` | A2C 系统（Computer） | A2C 配置的工具元数据（tags、auto_apply、alias 等） |
| `MCP_TOOL_ANNOTATION` | A2C 系统（Computer） | MCP 标准工具注解（destructive、readOnlyHint 等） |
| 其他任意 key | MCP Server 自身 | MCP Server 在 `Tool._meta` 中设置的原生元数据 |

!!! warning "为什么不将 a2c_tool_meta 展开到 meta 顶层？"

    MCP 协议的 `Tool._meta` 是一个开放字段，MCP Server 可以自由设置任意 key-value。
    如果将 `tags`、`auto_apply` 等 A2C 字段直接展开到 `meta` 顶层，一旦某个 MCP Server
    也在 `_meta` 中使用了同名 key（如 `tags`），就会产生**命名冲突**，Agent 端无法区分
    该字段来自 A2C 配置还是 MCP Server 自身。

    此外，`ToolMeta` 中包含 `ret_object_mapper: dict` 等嵌套类型，无法直接作为
    `AttributeValue` 存入。使用二级 key + JSON 字符串可以保证所有字段类型统一。

#### a2c_tool_meta 的值格式

`meta["a2c_tool_meta"]` 的值是一个 **JSON 字符串**（不是 dict），Agent 端需要 `json.loads()` 后使用：

```python
# Agent 端解析示例
import json

for tool in tools:
    meta = tool.get("meta", {})
    if "a2c_tool_meta" in meta:
        tool_meta = json.loads(meta["a2c_tool_meta"])
        tags = tool_meta.get("tags")          # list[str] | None
        auto_apply = tool_meta.get("auto_apply")  # bool | None
        alias = tool_meta.get("alias")        # str | None
```

#### 完整 JSON 示例

**场景 1**: `default_tool_meta = null`（未配置元数据）

```json
{
  "name": "hello",
  "description": "Say hello to someone.",
  "params_schema": {
    "properties": {
      "name": { "default": "World", "title": "Name", "type": "string" }
    },
    "title": "helloArguments",
    "type": "object"
  },
  "return_schema": {
    "properties": {
      "result": { "title": "Result", "type": "string" }
    },
    "required": ["result"],
    "title": "helloOutput",
    "type": "object"
  },
  "meta": {}
}
```

**场景 2**: `default_tool_meta = {"tags": ["browser"], "auto_apply": true}`

```json
{
  "name": "browser_navigate",
  "description": "Navigate to a URL.",
  "params_schema": { "..." : "..." },
  "return_schema": { "..." : "..." },
  "meta": {
    "a2c_tool_meta": "{\"auto_apply\": true, \"alias\": null, \"tags\": [\"browser\"], \"ret_object_mapper\": null}"
  }
}
```

!!! note "注意 a2c_tool_meta 的值类型"

    `a2c_tool_meta` 的值是 **JSON 字符串**，不是嵌套对象。
    对其执行 `json.loads()` 后得到如下 dict：

    ```json
    {
      "auto_apply": true,
      "alias": null,
      "tags": ["browser"],
      "ret_object_mapper": null
    }
    ```

### ToolMeta

工具元数据配置。此结构定义了 `a2c_tool_meta` JSON 字符串解析后的字段。

```python
class ToolMeta(TypedDict, total=False):
    auto_apply: NotRequired[bool | None]
    # 是否自动应用（跳过二次确认）

    ret_object_mapper: NotRequired[dict | None]
    # 返回值对象映射，用于统一不同 MCP 工具的返回格式

    alias: NotRequired[str | None]
    # 工具别名。仅替换 exposed_tool_name 的**工具名部分**，仍带 `{bundle_id}__` 前缀
    # （非对整个 exposed_tool_name 的完全覆盖）；见 [MCP Tool 命名与路由](#mcp-tool-命名与路由)

    tags: NotRequired[list[str] | None]
    # 工具标签，用于分类
```

### GetToolsReq

获取工具列表请求。

```python
class GetToolsReq(AgentCallData):
    agent: str      # Agent 名称
    req_id: str     # 请求 ID
    computer: str   # 目标 Computer 名称
```

### GetToolsRet

获取工具列表响应。

```python
class GetToolsRet(TypedDict):
    tools: list[SMCPTool]   # 工具列表
    req_id: str             # 请求 ID
```

---

### CallToolResult 结果级 A2C 标记 { #calltoolresult-结果级-a2c-标记 }

`client:tool_call` 的响应是 MCP 标准 `CallToolResult`（A2C **不可**改其结构）。A2C 通过 `CallToolResult` 的**结果级元数据字段**承载扩展标记。

!!! warning "元数据落位规则：结果级 `meta` vs 子级 `_meta`"

    A2C 在 MCP 结构上扩展元数据时，**线上字面 key 取决于层级**——以下约定与全部既有用法一致：

    | 层级 | 字面 wire key | 示例 |
    |------|--------------|------|
    | **结果级**（`CallToolResult` / `SMCPTool` 顶层）| `meta` | `meta.a2c_cancelled`、`meta.a2c_timeout`、授权失败的 `meta.error_code`（[4006/4007](error-handling.md#mcp-上游授权错误响应)）、`SMCPTool.meta.a2c_tool_meta` |
    | **子级**（`CallToolResult` content item）/ **MCP `Resource` / `Tool` 级** | `_meta` | content item `_meta.a2c_blob_handle`（[通用二进制传输](#通用二进制传输结构)）、`Resource._meta.fullscreen`（[Desktop](desktop.md)）、`Resource._meta.version`（[SKILL](skill.md)）|

    新增**结果级**标记 **MUST** 落 `meta`；**子级 / Resource 级**标记 **MUST** 落 `_meta`。

**取消 / 超时标记**（均为**结果级 `meta`** 下的 `a2c_*` 命名空间键）:

| key | 类型 | 必选性 | 含义 |
|-----|------|-------|------|
| `meta.a2c_cancelled` | bool | 取消时 **MUST** 为 `true` | 标识该结果由 `notify:tool_call_cancel` 中断产生（区别于普通失败/超时）|
| `meta.a2c_cancel_reason` | str | **SHOULD**（可选）| 诊断性原因，由 Computer 填写（当前恒为 `"agent_requested"`）；仅供观测，不承载控制逻辑 |
| `meta.a2c_timeout` | bool | 超时时 **SHOULD** 为 `true` | 标识该结果为超时返回（区别于取消）|

被取消时，Computer 对原 `client:tool_call` 的 ack 返回（参考实现 python，reference impl）:

```python
CallToolResult(
    content=[TextContent(text="Tool call cancelled", type="text")],
    isError=True,
    meta={"a2c_cancelled": True, "a2c_cancel_reason": "agent_requested"},
)
```

!!! note "Producer / Consumer 约定"

    Producer（Computer）**MUST** 把标记写在结果级 `meta`。Consumer（Agent）**SHOULD** 对 `meta` / `_meta` 两种线上 key 宽松读取（不同 SDK 序列化路径可能不同），并优先按本规范的结果级 `meta` 取值。配套时序见 [事件 §notify:tool_call_cancel](events.md#notifytool_call_cancel)。

---

## 房间管理结构

### 连接握手参数

Socket.IO 连接阶段的参数分**两个位置**承载，遵循"协议层放 URL、业务层放 auth"的分层原则：

#### URL Query 参数（协议层）

| 参数 | 必需 | 说明 |
|---|---|---|
| `a2c_version` | 是 | 协议版本号，格式 `MAJOR.MINOR.PATCH`，如 `0.2.0` |

由 Server **在 HTTP 中间件层** 校验；不兼容时返回 HTTP 400 携带 [`4008`](error-handling.md#协议版本不匹配4008) 错误 body。具体规则见 [协议版本与握手](versioning.md)。

#### `auth` 对象（业务层，ConnectAuth）

Socket.IO 连接握手阶段的 `auth` 对象。**所有客户端**（Agent / Computer）在连接 Server 时必须提供。由 Server 在 `connect` handler（业务代码）中处理。

##### 协议层最小契约

协议对 ConnectAuth **不设必需字段**——`auth` 是纯业务层对象。客户端角色（`role`）**不经连接握手 `auth` 声明**，而是在加入房间时经 [EnterOfficeReq](#enterofficereq)（`server:join_office`）的 `role` 字段建立，由 Server 据此路由：

```python
class ConnectAuth(TypedDict, total=False):
    # 协议不设必需字段；auth 为纯业务层对象。
    # 客户端角色（role）不在此声明——经 EnterOfficeReq / server:join_office 建立。
    token: str  # 业务层认证数据示例（非协议必需）
```

| 强度 | 行为约束 |
|------|---------|
| **MAY** | Client 在 `auth` 中放置业务层认证数据（token / API key / 用户标识等）；是否存在、是否被消费由**业务层**（Server 实现方）自决 |
| **SHOULD** | 避免把"已有协议事件承载的字段"重复塞进 `auth`。`role` / `office_id` / `name` 均已由 [EnterOfficeReq](#enterofficereq) 承载，重复放入 `auth` 会造成职责重叠与一致性维护负担；建议 `auth` 仅承载真正的认证数据（token / API key / 用户标识等）|

##### 业务层扩展空间

`connect` handler 是 Server 实现方编写的业务代码，A2C-SMCP 协议**不约束**业务层在 `auth` 中放什么、怎么校验。常见扩展场景：

- 鉴权 token：`auth = {"token": "..."}`
- 多租户标识：`auth = {"tenant_id": "..."}`
- 网关签名：`auth = {"signature": "..."}`

这些都属于业务层职责，协议不评价。SDK 实现方提供的默认行为应只发送业务层认证数据（如 `token`），`role` 经 `server:join_office` 声明；并提供回调让用户注入业务字段。

!!! note "为什么 a2c_version 不在 auth 里"

    协议版本校验必须在任何业务代码之前完成，不能受 `connect` handler 实现的影响。因此 `a2c_version` 放在 URL query（HTTP 层），由独立中间件校验；`auth` 仅承载业务层数据。详见 [协议版本与握手 § 设计取向](versioning.md#设计取向)。

### EnterOfficeReq

加入房间请求。**不再**携带版本信息——版本校验已在连接建立前完成（HTTP 层）。客户端角色（`role`）即经本请求的 `role` 字段声明（连接握手 `auth` 不承载 `role`），由 Server 据此路由。

```python
class EnterOfficeReq(TypedDict):
    role: Literal["computer", "agent"]  # 角色类型
    name: str                           # 名称
    office_id: str                      # 房间 ID
```

### LeaveOfficeReq

离开房间请求。

```python
class LeaveOfficeReq(TypedDict):
    office_id: str      # 房间 ID
```

### EnterOfficeNotification

成员加入房间通知。

```python
class EnterOfficeNotification(TypedDict, total=False):
    office_id: str              # 房间 ID
    computer: str | None        # 加入的 Computer 名称（若为 Computer）
    agent: str | None           # 加入的 Agent 名称（若为 Agent）
```

### LeaveOfficeNotification

成员离开房间通知。

```python
class LeaveOfficeNotification(TypedDict, total=False):
    office_id: str              # 房间 ID
    computer: str | None        # 离开的 Computer 名称
    agent: str | None           # 离开的 Agent 名称
```

### ListRoomReq

列出房间内会话请求。

```python
class ListRoomReq(AgentCallData):
    agent: str          # Agent 名称
    req_id: str         # 请求 ID
    office_id: str      # 房间 ID
```

### SessionInfo

会话信息。

```python
class SessionInfo(TypedDict, total=False):
    sid: str                                # 会话 ID
    name: str                               # 会话名称
    role: Literal["computer", "agent"]      # 角色
    office_id: str                          # 所属房间 ID
    a2c_version: str                        # 协议版本号（Server 在 HTTP 握手阶段从 URL query 记录）
```

!!! note "a2c_version 字段"

    - Server 在客户端 Socket.IO 连接的 HTTP 校验阶段从 URL query 的 `a2c_version` 读取并存入 Session
    - 同房间内 `a2c_version` 必然兼容（Server 在 HTTP 层已校验）；此字段仅用于**展示与诊断**（如 UI 显示成员版本、日志定位）
    - 不用于二次校验
    - 详见 [协议版本与握手](versioning.md)

### ListRoomRet

列出房间内会话响应。

```python
class ListRoomRet(TypedDict):
    sessions: list[SessionInfo]     # 会话列表
    req_id: str                     # 请求 ID
```

---

## 配置相关结构

### UpdateComputerConfigReq

配置更新请求。同时被 Desktop 更新事件（`server:update_desktop` / `notify:update_desktop`）与 SKILL 更新事件（`server:update_skills` / `notify:update_skills`）复用。

```python
class UpdateComputerConfigReq(TypedDict):
    computer: str       # Computer 名称
```

**复用说明**: 此数据结构被以下事件共用：

| 事件 | 用途 |
|------|------|
| `server:update_config` | Computer 配置更新请求 |
| `server:update_desktop` | 桌面更新通知请求 |
| `notify:update_desktop` | 桌面更新广播通知 |
| `server:update_skills` | SKILL 更新通知请求 |
| `notify:update_skills` | SKILL 更新广播通知 |

### UpdateMCPConfigNotification

配置更新通知。

```python
class UpdateMCPConfigNotification(TypedDict, total=False):
    computer: str       # Computer 名称
```

### UpdateToolListNotification

工具列表更新通知。

```python
class UpdateToolListNotification(TypedDict, total=False):
    computer: str       # Computer 名称
```

### GetComputerConfigReq

获取 Computer 配置请求。

```python
class GetComputerConfigReq(AgentCallData):
    agent: str          # Agent 名称
    req_id: str         # 请求 ID
    computer: str       # 目标 Computer 名称
```

### GetComputerConfigRet

获取 Computer 配置响应。

```python
class GetComputerConfigRet(TypedDict):
    inputs: NotRequired[list[MCPServerInput] | None]    # 输入定义列表
    servers: dict[str, MCPServerConfig]                 # key = bundle_id（server 唯一身份，非 name）
```

---

## Desktop 相关结构

### GetDeskTopReq

获取桌面信息请求。

```python
class GetDeskTopReq(AgentCallData, total=True):
    agent: str                      # Agent 名称
    req_id: str                     # 请求 ID
    computer: str                   # 目标 Computer 名称
    desktop_size: NotRequired[int]  # 可选：限制返回的桌面内容数量
    window: NotRequired[str]        # 可选：指定获取的 WindowURI（完全相等匹配；未命中返回空，非错误）
```

### Desktop

桌面内容类型别名。每个 `Desktop` 条目是一个字符串，代表一个窗口的渲染结果。

```python
Desktop: TypeAlias = str
```

**内容格式**:

- 有文本内容时：`{window:// URI}\n\n{body}`（多个 `TextResourceContents` 的 `text` 用 `\n\n` 连接）
- 无文本内容时：仅 `{window:// URI}`

**示例**:

```
window://com.example.browser/main

<html>当前页面内容...</html>
```

详见 [Desktop 桌面系统](desktop.md) 中的完整规范。

!!! note "Desktop 更新事件的数据结构"

    `server:update_desktop` 和 `notify:update_desktop` 事件均复用 [`UpdateComputerConfigReq`](#updatecomputerconfigreq) 结构（仅包含 `computer: str` 字段），与 `server:update_config` 共享同一数据结构。

### GetDeskTopRet

获取桌面信息响应。

```python
class GetDeskTopRet(TypedDict, total=False):
    desktops: list[Desktop]     # 桌面内容列表（字符串形式）
    req_id: str                 # 请求 ID
```

---

## Resource 发现相关结构

### GetResourcesReq

枚举指定 MCP Server 的 Resource 列表请求——透明转发 MCP 标准 `resources/list`，**不做协议级过滤**。Agent 据此发现 window / 业务自定义 scheme 的资源。

```python
class GetResourcesReq(AgentCallData, total=True):
    agent: str                          # Agent 名称
    req_id: str                         # 请求 ID
    computer: str                       # 目标 Computer 名称
    mcp_server: str                     # 必填：目标 MCP Server 的 bundle_id（= client:get_config 返回的 servers 字典 key）
    cursor: NotRequired[str]            # 可选：MCP 标准 cursor 翻页；首次不传或传 null
```

### GetResourcesRet

```python
class GetResourcesRet(TypedDict, total=False):
    resources: list[Resource]           # MCP 标准 Resource 列表（含任意 scheme，业务自决过滤）
    next_cursor: NotRequired[str]       # 可选：有则继续翻页；无则结束
    req_id: str                         # 请求 ID
```

!!! note "透明转发原则"

    Computer 不做 scheme / 元数据层面的过滤、不做跨 Server 聚合——业务方按 Server 维度
    遍历，自决过滤条件（`window://` / `_meta` 字段 / 名称匹配等）。
    **保留 MCP 标准 cursor 翻页能力**，业务方按需翻页，不强制全量加载。

    - `mcp_server` 不存在 → `4014 MCP Server Not Found`
    - MCP Server 不支持 `resources` capability → `4015 MCP Capability Not Supported`

!!! note "v0.2 不返回 resourceTemplates"

    `client:get_resources` 仅对应 MCP `resources/list`，**不返回** resourceTemplates。MCP 上游有独立端点 `resources/templates/list`——v0.2 用户场景（window 静态资源发现等）不需要 URI 模板能力，未来 v0.3+ 如有需要将增加 `client:get_resource_templates` 独立事件。

### A2CResource

A2C 协议定义的 Resource 类型——结构镜像 MCP `Resource`，但字段命名沿用 A2C snake_case 风格。

```python
class A2CResource(TypedDict, total=False):
    uri: str                            # 必选：访问 URI（任意 scheme）
    name: NotRequired[str]              # 可选：人类可读的资源名
    description: NotRequired[str]
    mime_type: NotRequired[str]
    size: NotRequired[int]              # 可选：字节数
    annotations: NotRequired[dict]      # 透传 MCP annotations（含 audience 等）
    _meta: NotRequired[dict]            # 协议扩展点
```

---

## SKILL 相关结构

SKILL 通道的请求 / 响应结构。完整通道语义（命名规则、URI、source 模式、安装生命周期、安全模型）见 [SKILL 通道](skill.md)。

### A2CSkillRef

Skill 引用对象——`client:get_skills` 返回列表的元素。`name` 是协议主键（合成的全局唯一名，跨工具对齐裸名：marketplace `<plugin>:<skill>` / user 裸 `<skill>` / mcp `mcp:<server>:<skill>`，见 [skill.md §1](skill.md#1-skill-命名)）；Agent 把 `name` 当**不透明可比较字符串**，判定来源用 `source` 字段。

```python
class A2CSkillRef(TypedDict):       # 默认 total=True：裸字段 = 必选，NotRequired[] = 可选
    # ── 主键 ────────────────────────────────────────────
    name: str                       # 必选：合成全局唯一名（跨工具对齐裸名）
                                    # marketplace: acme-audit:audit / user: my-helper
                                    # mcp: mcp:tfrobot-tools:code-review
    # ── 来源元数据 ───────────────────────────────────────
    source: str                     # 必选：完整来源 provenance（含 marketplace 名等）
                                    # 例：mcp:tfrobot-tools / marketplace:acme-skills / user
    uri: NotRequired[str]           # 仅 MCP 来源：skill://host/skill-name
                                    # 来源追溯用次要身份，Agent 非权威（见 skill.md §2）
    # ── 物化输出 ─────────────────────────────────────────
    path: str                       # 必选：Computer 本地绝对目录路径
                                    # staging 落盘是所有 source 的统一第一步，故恒存在
                                    # 面向 Agent SDK（脚本执行/文件访问）；渲染期可经 ${TFROBOT_SKILL_DIR} 展开为 LLM-facing（skill.md §9.4）
    # ── SKILL.md frontmatter 派生（marketplace v1 §3.1 的 6 字段，无 version）──
    description: str                # 必选：marketplace SKILL v1 §3.1
    license: NotRequired[str]
    compatibility: NotRequired[str]
    allowed_tools: NotRequired[list[str]]   # frontmatter "allowed-tools" 规范化为 list
    skill_metadata: NotRequired[dict]       # frontmatter.metadata 透传；A2C 不解释
    # ── 包元数据派生（非 frontmatter）────────────────────
    version: NotRequired[str]               # 来源各异（见下方 note）；user 源缺省/null
```

!!! note "必选核心 = `name` / `source` / `path` / `description`（4 字段）"

    这四个字段跨**所有 source**（marketplace / user DropIn / mcp）恒存在，是 `A2CSkillRef` 的必选核心：

    - `name` / `source`：协议主键与来源 provenance，每条 ref 必有。
    - `path`：staging 物化是所有 source 的统一第一步，进入 Registry 的 SKILL 必有可读本地目录（见下方 note）。
    - `description`：SKILL.md frontmatter 强制字段（marketplace v1 §3.1 的 6 字段之一），任何合法 SKILL.md 必含。

    其余 6 个（`uri` / `license` / `compatibility` / `allowed_tools` / `skill_metadata` / `version`）为 `NotRequired`。Producer（Computer）**MUST** 发齐 4 个必选字段；Consumer（Agent）可假定其存在，但 **MUST NOT** 假定任一可选字段存在。SDK 用 PEP 655 跟进时，两种等价写法皆可——本规范取 house 约定（`total=True` 默认 + `NotRequired[]`），SDK 亦可用 `total=False` + `Required[]`。

!!! note "`path` 恒存在；为何无 raw `mcp_server` 字段"

    **`path` 必选**：Computer 是 SKILL 管理者，所有 source 落地的统一第一步都是 staging 物化到本地（skill.md §4/§5），故进入 Registry 的 SKILL 必有可读本地目录，不存在"无 baseDir"形态。

    **不暴露原始 MCP server 名**：理念 #2 要求 Agent 侧协议表面与 source 无关。raw（未规范化）server 名是 MCP 工具/资源通道的寻址键（`client:get_config` 的 `servers` key），与 SKILL 不同层级，不反规范化进 SKILL ref。来源追溯由 `source` 与 MCP 来源的 `uri`（skill.md §2）承担。

!!! note "`version` 的 source-of-truth（不来自 frontmatter）"

    marketplace SKILL v1 frontmatter 恰好 6 字段（`name` / `description` / `license` / `compatibility` / `metadata` / `allowed-tools`），**无 version**。`A2CSkillRef.version` 按来源取值，故为 `NotRequired`（无来源即省略）：

    | Source | `version` 来源 |
    |---|---|
    | marketplace | `plugin.json` / marketplace entry 的 version |
    | mcp | `skill://` 资源的 `_meta.version`（[skill.md §3](skill.md#3-mcp-server-端-source-模式声明) 推荐附加字段） |
    | user | 无可靠来源 → **缺省 / null** |

    Agent **MUST NOT** 假定 `version` 一定存在。

### GetSkillsReq

获取 SKILL 清单请求。

```python
class GetSkillsReq(AgentCallData, total=True):
    agent: str          # Agent 名称
    req_id: str         # 请求 ID
    computer: str       # 目标 Computer 名称
```

### GetSkillsRet

获取 SKILL 清单响应——轻量元数据，**不含** SKILL.md body。

```python
class GetSkillsRet(TypedDict, total=False):
    skills: list[A2CSkillRef]   # 当前已安装且可用 SKILL（排除孤儿；不排序、不去重）
    req_id: str                 # 请求 ID
```

### GetSkillReq

获取 SKILL 包内单个资源请求。SKILL 本质是文件夹：`rel_path` 缺省取包根 `SKILL.md`（入口），携带 `rel_path` 取包内其它资源，实现渐进式披露。传输机制不在此处——二进制 / 过大文本由 `GetSkillRet.blob_handle` 转 [通用二进制传输](blob-transfer.md)。

```python
class GetSkillReq(AgentCallData, total=True):
    agent: str                  # Agent 名称
    req_id: str                 # 请求 ID
    computer: str               # 目标 Computer 名称
    name: str                   # 必选：来自某 A2CSkillRef.name
    rel_path: NotRequired[str]  # 可选：SKILL 包根 POSIX 相对路径
                                # 缺省 = "SKILL.md"；MUST 相对、无 ..、无绝对路径
```

### GetSkillRet

获取 SKILL 包内单个资源响应。文本且可内联 → `body` 直接给出；二进制或过大文本 → `blob_handle` 转 [`client:get_blob`](blob-transfer.md) 拉取——`body` 与 `blob_handle` **恰一存在**。

```python
class GetSkillRet(TypedDict, total=False):
    name: str                       # 回显
    rel_path: str                   # 回显（缺省请求时为 "SKILL.md"）
    mime_type: str                  # 资源 MIME，如 text/markdown / image/png（确定性推断，见 SKILL §6.4）
    total_size: int                 # 资源总字节数
    sha256: str                     # 全量资源 sha256 十六进制（完整性 + 变更检测）
    body: NotRequired[str]          # 文本且 ≤ 内联预算：直接内容（与 blob_handle 恰一）
    blob_handle: NotRequired[str]   # 否则：转 client:get_blob 的不透明句柄（与 body 恰一）
    req_id: str                     # 请求 ID
```

!!! note "「资源字节」的定义（total_size / sha256 / 传输的基准）"

    `total_size` / `sha256` 及（走 handle 时的）分块一律基于 **Agent 最终消费的资源字节**：SKILL.md → **frontmatter 剥离后的 body**；其它文件 → 原始文件字节。frontmatter 剥离、占位符**不展开**在确定资源字节时已完成。空资源 = `total_size=0`，文本走空 `body`。

!!! note "内联 vs handle 的判定"

    Computer 解析 `rel_path` 后：**[文本 MIME](skill.md#64-mime_type-确定性与文本-mime判据) 且 `total_size` ≤ 内联预算**（保证单条 ack 不超 Server buffer）→ `body`；**二进制 MIME，或文本超内联预算** → 仅给 `blob_handle`（不内联任何字节）。`body` / `blob_handle` 恰一；Agent **SHOULD** 用 `sha256` 校验 `body`，或在 handle 路径于 `eof` 后校验。`mime_type` **MUST** 确定性推断、不依赖宿主 OS 的 MIME 注册表（见 [SKILL §6.4](skill.md#64-mime_type-确定性与文本-mime判据)）。

!!! note "安全边界与 too_large"

    `rel_path` 沙箱（穿越 / `.skillenv` / 不存在）与绝对上限（`too_large`）在 **get_skill 解析时** 决断 → [`4017`](error-handling.md#skill-resource-not-accessible4017)，**不**铸造 handle、零字节传输。占位符不展开（Agent SDK 职责，见 [SKILL §7](skill.md#7-事件)）。详见 [SKILL §9](skill.md#9-安全模型)。

---

## 通用二进制传输结构

通用 Agent←Computer 字节拉取通道的结构。完整语义（句柄契约、生产者-消费者模型、安全模型）见 [通用二进制传输](blob-transfer.md)。

### BlobHandle

```python
BlobHandle: TypeAlias = str   # 不透明、Computer 铸造、无状态可重解析
```

由某生产者通道在其响应中铸造。Agent 视为**不透明**：MUST NOT 解析 / 拼接 / 伪造。Computer 每次调用即时解析，**无 session / 无 TTL**；解析时**重新施加铸造通道的鉴权**（SKILL → §9 沙箱）。

载体随响应结构而异，**语义与拉取契约完全一致**（详见 [通用二进制传输 §5](blob-transfer.md#5-生产者通道接入契约)）：

| 生产者 | 句柄载体 | 对等元数据 |
|---|---|---|
| `GetSkillRet`（A2C 可变） | 顶层 [`blob_handle`](#getskillret) | 顶层 `total_size` / `sha256` / `mime_type` |
| MCP `CallToolResult`（标准不可变） | content item `_meta.a2c_blob_handle` | item `_meta.a2c_total_size` / `_meta.a2c_sha256` + 既有 `mimeType` |

`_meta` 旁路与 [`SMCPTool.meta` 命名空间约定](#smcptoolmeta-序列化规范)（`a2c_tool_meta` 等）同构——A2C 在不可变 MCP 结构上扩展的既定手法。

### GetBlobReq

```python
class GetBlobReq(AgentCallData, total=True):
    agent: str                          # Agent 名称
    req_id: str                         # 请求 ID
    computer: str                       # 目标 Computer 名称
    blob_handle: str                    # 必选：来自某通道响应的不透明句柄
    chunk_offset: NotRequired[int]      # 可选：资源字节绝对偏移；缺省 0
                                        # 无状态幂等 → 可续传 / 重试 / 并行
    max_chunk_bytes: NotRequired[int]   # 可选：客户建议单块上限
                                        # Computer clamp（不超 Server buffer）
```

### GetBlobRet

```python
class GetBlobRet(TypedDict, total=False):
    blob_handle: str            # 回显
    mime_type: str              # 资源 MIME
    total_size: int             # 资源总字节数（首块即知；一次读取内恒定）
    sha256: str                 # 全量资源 sha256 十六进制（跨块恒定）
    chunk_offset: int           # 本块起始字节偏移
    eof: bool                   # ⟺ chunk_offset + 本块字节数 == total_size
    blob: str                   # base64，本块字节
    req_id: str                 # 请求 ID
```

!!! note "完整性 / 一致性 / 演进缝隙"

    - `eof` 后 Agent **SHOULD** 校验重组 sha256 == 响应 `sha256`，不符即损坏、重读。
    - `sha256` / `total_size` 一次逻辑读取内 **MUST** 稳定；跨块变化 ⇒ 源被改写，Agent **MUST** 从 offset 0 重读。Computer **SHOULD** 尽力一致快照。
    - `GetBlobReq` / `GetBlobRet` 为开放 TypedDict，未来可**非破坏**追加 `content_encoding`（gzip 等，缺省 identity）/ `etag`；offset / total_size / sha256 基于**解码后**资源字节，加压缩不致歧义。
    - 句柄失效 / 源消失 / 范围越界 → [`4018`](error-handling.md#blob-not-accessible4018)。

---

## MCP Server 配置结构

### BaseMCPServerConfig

MCP Server 配置基类。

```python
class BaseMCPServerConfig(TypedDict):
    name: str
    # MCP Server 名称（纯 display，人类可读）。允许碰撞、永不做键/寻址、不强制唯一；唯一身份见 bundle_id

    bundle_id: NotRequired[str | None]
    # MCP Server 唯一标识（软件级 BundleID）。省略时由 name 经确定性算法生成，解析后恒有值。
    # 同一 bundle_id 视为同一软件，不允许多开。命名/生成/去重/路由见「MCP Tool 命名与路由（BundleID 模型）」。

    disabled: bool
    # 是否禁用

    forbidden_tools: list[str]
    # 禁用的工具列表

    tool_meta: dict[str, ToolMeta]
    # 工具元数据映射（工具名 → 元数据）

    default_tool_meta: NotRequired[ToolMeta | None]
    # 默认工具元数据，当具体工具未配置时使用

    vrl: NotRequired[str | None]
    # VRL 脚本，用于动态转换工具返回值
```

### MCPServerStdioConfig

标准输入输出模式的 MCP Server 配置。

```python
class MCPServerStdioParameters(TypedDict):
    command: str
    # 启动命令

    args: list[str]
    # 命令行参数

    env: dict[str, str] | None
    # 环境变量

    cwd: str | None
    # 工作目录

    encoding: str
    # 文本编码，默认 utf-8

    encoding_error_handler: Literal["strict", "ignore", "replace"]
    # 编码错误处理方式


class MCPServerStdioConfig(BaseMCPServerConfig):
    type: Literal["stdio"]
    server_parameters: MCPServerStdioParameters
```

### MCPServerStreamableHttpConfig

Streamable HTTP 模式的 MCP Server 配置。

```python
class MCPServerStreamableHttpParameters(TypedDict):
    url: str
    # 端点 URL

    headers: dict[str, Any] | None
    # 请求头

    timeout: str
    # HTTP 超时（ISO 8601 duration 格式）

    sse_read_timeout: str
    # SSE 读取超时（ISO 8601 duration 格式）

    terminate_on_close: bool
    # 关闭时是否终止客户端会话


class MCPServerStreamableHttpConfig(BaseMCPServerConfig):
    type: Literal["streamable"]
    server_parameters: MCPServerStreamableHttpParameters
```

### MCPSSEConfig

SSE 模式的 MCP Server 配置。

```python
class MCPSSEParameters(TypedDict):
    url: str
    # 端点 URL

    headers: dict[str, Any] | None
    # 请求头

    timeout: float
    # HTTP 超时（秒）

    sse_read_timeout: float
    # SSE 读取超时（秒）


class MCPSSEConfig(BaseMCPServerConfig):
    type: Literal["sse"]
    server_parameters: MCPSSEParameters
```

### MCPServerConfig

MCP Server 配置联合类型。

```python
MCPServerConfig = MCPServerStdioConfig | MCPServerStreamableHttpConfig | MCPSSEConfig
```

**注意**: MCP Server 类型为 `"stdio"`, `"streamable"`, `"sse"` 三种，其中 `"streamable"` 对应 MCP 官方的 Streamable HTTP 传输模式。

---

## MCP Tool 命名与路由（BundleID 模型） { #mcp-tool-命名与路由 }

Computer 聚合多个 MCP Server 时，工具名可能跨 Server / marketplace / plugin 重名。由于所有主流 LLM provider 的工具接口**只靠扁平名称区分、无 namespace/分类字段**（Anthropic `^[a-zA-Z0-9_-]{1,128}$`、OpenAI `^[a-zA-Z0-9_-]{1,64}$`，均拒 `.`），A2C 以 **BundleID 模型**为每个聚合工具生成稳定、唯一、provider 兼容的 `exposed_tool_name`。

模型对齐人类世界的软件包管理：一个 **MCP Tool** = 软件的一个功能；一个 **MCP Server** = 一个软件，拥有唯一包标识 **BundleID**。

### BundleID（软件唯一标识） { #bundleid }

- `bundle_id`（[BaseMCPServerConfig](#basemcpserverconfig)）是 MCP Server 的**唯一身份**（软件级）。SDK 管理 MCP 服务的身份 **MUST** 使用 `bundle_id`，**MUST NOT** 使用 `name`。
- **字符集**：`[A-Za-z0-9_-]`。
    - **MUST NOT** 含 `.`（provider 侧 tool name 拒 `.`；且 `.`→`_` 清洗非单射）。
    - **MUST NOT** 含连续下划线 `__`（`__` 是 BundleID 与工具名的保留分隔符，见[唯一性](#bundleid-唯一性)）。

#### 身份正交性：bundle_id vs MCP host vs name { #identity-orthogonality }

A2C 体系存在多类 identifier，**互不相干、勿混用**：

| identifier | 谁定 | 用途 | 是否 A2C server 身份 |
|---|---|---|---|
| **`bundle_id`** | 配置人员 / 缺省生成 | A2C server 唯一身份：`get_config` 字典 key、`get_resources.mcp_server`、`4014` / `4015`、`4006` / `4007` 的 `meta.mcp_server` | **是（唯一）** |
| **`name`** | 配置人员 | 纯 display（人类可读）：**允许碰撞、永不做键/寻址、不强制唯一** | 否 |
| **MCP resource host**（`window://<host>` / `skill://<host>` 的 `host`）| **MCP Server 自选**（反向域名风格）| MCP `resources/list` 的 URI 命名空间；A2C **透传不解释** | 否（正交）|
| **SKILL name 的 `<server>` 段**（`mcp:<server>:<skill>`）| 规范化 MCP-source server 名（[skill.md §1](skill.md#1-skill-命名)，Claude Code 对齐）| SKILL 全局唯一合成名的一段；自管唯一（§1.5）| 否（正交）|

- 一个 A2C server（`bundle_id`）内可含多个 MCP-自选 host 的资源；把 server 身份换成 `bundle_id` **与 `window://` / `skill://` / SKILL name 零耦合**。
- 因 `get_config.servers` 的 key 现为 `bundle_id`，`name` 的旧隐式唯一性（曾作 dict key）**随之撤回**——`name` 可碰撞，仅供展示。

#### 缺省生成（确定性） { #bundleid-缺省生成 }

`bundle_id` 省略时，SDK **MUST** 按下述算法从 `name` 派生。算法**逐字节确定性**，各 SDK（Python / Rust）**MUST** 产出同一结果——一致性由[一致性测试向量](#bundleid-conformance)强制。生成在**加载 / 注册期**完成（derive-on-load），**MUST NOT** 回写配置源（如 `mcp.json`）。

**Step 1 — 规范化 `name`**（按 **Unicode 码点**迭代，Python `for c in name` / Rust `.chars()`；**MUST NOT** 按 UTF-8 字节或 grapheme cluster 迭代）：

1. 凡不属于 ASCII 字符类 `[A-Za-z0-9_-]` 的码点（任何非 ASCII 一律命中）→ 替换为 `_`。**MUST** 用显式 ASCII 类，**MUST NOT** 用 `\w`（各语言 Unicode `\w` 集合不一致）。
2. 折叠连续的 `_`（**含**原文中已有的 `__`）为单个 `_`；**不折叠** `-`。
3. 裁剪首尾的 `[_-]`。
4. **不做**大小写折叠（`MyServer` ≠ `myserver`）。

**Step 2 — 取值**：Step 1 结果**非空** → 即 `bundle_id`。

**Step 3 — fallback**（Step 1 结果为空，如 `name` 全为符号 / CJK / 空串）：`bundle_id = "bundle_" + lowercase_hex(SHA-256(digest_input)[:8])`（即 `bundle_` + 16 个小写 hex 字符）。
- `digest_input` = 该 Server 的 [connection-identity 字节串](#connection-identity)（**不**用 `name`——它已被证明无法产出合法值）。
- Hash **MUST** 为 SHA-256；**MUST NOT** 用语言内建 `hash()`（进程级随机化）或任何非密码学 hash。编码 **MUST** 为小写 hex（**禁** base32 / base64——大小写 / padding 有跨实现变体）。

!!! warning "缺省生成 MUST NOT 使用随机 UUID"

    随机 UUID 会**同时**破坏「跨 SDK 逐字节一致」与「重启稳定性」（进程重启后 exposed_tool_name 漂移，Agent 侧全套工具改名）。fallback **MUST** 为确定性摘要。

> **规范化非单射**：`my server` / `my-server` / `my_server` 均 → `my_server`；两个都叫 `everything` 的 Server 均 → `everything`。因此过去按 `name` 不冲突的配置，缺省生成后可能得到相同 `bundle_id` → 属 [no-double-open](#no-double-open) 冲突，走[配置诊断](#config-diagnostics)，由配置人员显式指定 `bundle_id` 解决。

#### connection-identity 字节串 { #connection-identity }

Step 3 fallback 摘要的输入。为避免 JSON 跨语言序列化漂移（转义 / 数字形态 / key 排序），**MUST** 用长度前缀（TLV）字节帧、**MUST NOT** 用 JSON。仅纳入**连接建立字段**：

| type | 纳入字段（顺序固定） |
|------|--------------------|
| `stdio` | `type` + `command` + `args`（保序）+ `env`（按 key 码点序排序）|
| `streamable` / `sse` | `type` + `url` + `headers`（按 key 码点序排序）|

- **排除**：`disabled` / `tool_meta` / `forbidden_tools` / `vrl` / `env_file` / `cwd` / `encoding` / `timeout` 系列——非连接身份，或跨语言类型不一致（如 `timeout` 在 `streamable` 为 ISO-8601 字符串、在 `sse` 为 float）。
- 编码 UTF-8；`args` **保序**（参数顺序有语义）；`env` / `headers` 按 key 码点序排序（**纳入** env / headers 以区分仅凭连接凭证不同的无名 Server）。空 `args` / `env` → 空集。
- 精确字节帧（TLV 长度前缀、空值表示、分隔符常量）由[一致性测试向量](#bundleid-conformance)定死。

!!! important "摘要输入取 raw（占位符 / secret 注入前）"

    connection-identity 的所有字段 **MUST** 取 **raw / 未注入**配置——`${input:*}` / `${env:*}` / secret 占位**按字面**参与摘要，**MUST NOT** 先渲染再摘要。推论：`bundle_id` 派生（及其作为 [no-double-open](#no-double-open) 去重键）整体在 **raw 配置**上完成，**跨阶段一致**（bundled 恢复 / manager 注册期同键，不因渲染时机分歧）。

    - **稳定性**：轮换被 `env` / `headers` 引用的 `${input:*}` / secret **不改** raw → `bundle_id` 稳定 → `exposed_tool_name` 不漂移（契合 [§缺省生成](#bundleid-缺省生成) 的 warning）。取 rendered 则轮换即令 Agent 侧全套工具「改名」。
    - **代价**：两个「仅解析后 secret 不同、占位相同」的无名 Server 会撞同一 `bundle_id` → [no-double-open](#no-double-open) 冲突，由配置人员显式指定 `bundle_id` 消歧（无名 + 相同占位属边角场景）。

#### 一致性测试向量（规范夹具） { #bundleid-conformance }

`bundle_id` 缺省生成的跨 SDK 逐字节一致，由**协议仓托管的一致性测试向量**强制：`(name, connection config) → 期望 bundle_id`。向量 **MUST** 覆盖分叉点——CJK `name`、符号 `name`、含原文 `__` 的 `name`、空名 + `stdio`、空名 + `http/sse`。所有 SDK 实现 **MUST** 通过该夹具方为合规。

**规范夹具**：[`fixtures/bundle_id_conformance_vectors.json`](fixtures/bundle_id_conformance_vectors.json)（rust-sdk 首版、python-sdk 对拍锁定）。向量以**扁平连接身份形式**表达（`type` + `command`/`args`/`env` 或 `url`/`headers`），与各 SDK 的 config serde 形态解耦；文件内 `algorithm` 段固化 TLV 精确字节帧（u32-BE 长度前缀、key 升序、`type` 判别符 `stdio`/`streamable`/`sse`）。

> 参考实现与向量由 rust-sdk 首版提供、python-sdk 对拍锁定，随协议一并落库。

### exposed_tool_name { #exposed_tool_name }

聚合后对外暴露、进入 LLM 工具声明的工具名，即 `SMCPTool.name`（[GetToolsRet](#gettoolsret)）：

```text
exposed_tool_name = bundle_id + "__" + (alias ?? original_tool_name)
```

- 所有聚合工具**恒**以 `{bundle_id}__` 开头，归属一眼可辨。
- `alias`（[ToolMeta.alias](#toolmeta)）仅替换**工具名部分**，仍带 `{bundle_id}__` 前缀。
- 协议**不采用**「仅冲突时改名」；恒用 BundleID 前缀，避免加载顺序 / server 集合变化导致名称漂移。

#### 唯一性与可解析性 { #bundleid-唯一性 }

- `bundle_id` 不含 `__`，故 `exposed_tool_name` 对 `(bundle_id, tool)` **单射**：`bundle_id` 恒为**第一个 `__` 之前的前缀**。
- 因此**原始工具名内部允许 `__`**（无需限制）：`b__foo__bar` 必然解析为 `bundle_id=b` / `tool=foo__bar`。
- 反例（为何禁 BundleID 的 `__`）：若允许 `bundle_id=a__b`，则 `(a__b, c)` 与 `(a, b__c)` 均产出 `a__b__c` → 两个唯一 BundleID 撞同名。禁 `__` 即消除歧义。

!!! note "归属靠映射表，不靠字符串 split"

    `alias` 不可逆推 `original_tool_name`，故**路由 MUST 依赖 [ExposedToolMapping](#exposedtoolmapping)**，**MUST NOT** 对 `exposed_tool_name` 做字符串 split 反解身份。

### 去重：no-double-open { #no-double-open }

- **同一 `bundle_id` = 同一软件，任一时刻只对应一个 Server，MUST NOT 多开。**
- **加载期（boot / 整表加载）**：重复 `bundle_id`（**无论** connection config 是否相同）**MUST** 视为冲突——仅保留**配置顺序第一个**并启动，其余由 Computer 作[配置诊断](#config-diagnostics)（日志 / 本地 UI）报告，**MUST NOT** 静默丢弃。
- **运行期（显式 add / update 单个 Server）**：传入已存在的 `bundle_id` **MUST** 按 `bundle_id` **原地更新**（intentional replace；`name` 可变、`bundle_id` 稳定），**不**算冲突——每个 `bundle_id` 仍只对应一个 Server，不破 no-double-open。
- 确需多实例（如同一浏览器工具的共享 / `--isolated` 两套）→ **以不同 `bundle_id` 表达**（`bundle_id` 由配置人员自由指定）。

### ExposedToolMapping { #exposedtoolmapping }

Computer 侧维护的路由映射；`client:get_tools` 与 `client:tool_call` **MUST** 共享同一份：

```python
class ExposedToolRoute(TypedDict):
    bundle_id: str                  # 归属 MCP Server 唯一标识
    server_name: str                # MCP Server 人类可读名（display / 诊断用，非唯一、非身份）
    original_tool_name: str         # MCP 上游注册的原始工具名（路由目标）
    alias: NotRequired[str | None]  # 若配置了别名

# exposed_tool_name -> route
ExposedToolMapping = dict[str, ExposedToolRoute]
```

- `client:get_tools` 返回的 `SMCPTool.name` 为 `exposed_tool_name`。
- `client:tool_call` 的 `tool_name` 传入 `exposed_tool_name`；Computer **MUST** 经此表路由到 `bundle_id` + `original_tool_name` 调用上游 MCP。命中失败 → [`4001`](error-handling.md#工具调用错误码)。

### 长度与 provider 适配

- A2C 协议**不限制** `exposed_tool_name` 长度。不同 provider 上限不同（Anthropic 128 / OpenAI 64 / 部分兼容接口几乎不限），只有 Agent 知道对面是哪个 LLM。
- **provider 长度合规属 Agent 业务 / 集成层职责，不属协议、不强制进 SDK**：当下游 provider 有限长且 `exposed_tool_name` 超限时，集成层 **MUST** 维护 `短名 ↔ exposed_tool_name` 的**双射**映射、在工具调用回程逆转；短名生成 **MUST** collision-safe（带摘要后缀，**禁裸截断**——两个长名截同前缀会相撞）。
- **SDK MUST 保持 wire-faithful**：`exposed_tool_name` 原样上 wire、不限长、不改名；SDK **MAY** 提供可选短名 helper，但短名策略 provider-specific，由集成层启用。
- **A2C wire 恒传 `exposed_tool_name`**；短名仅存在于 Agent↔LLM 之间，**MUST NOT** 出现在任何 A2C 事件载荷中（保三角色纯净）。

> `forbidden_tools`（[BaseMCPServerConfig](#basemcpserverconfig)）**MAY** 按 `original_tool_name` 或 `exposed_tool_name` 匹配禁用。

### 配置诊断（Computer 本地，非协议错误码） { #config-diagnostics }

下列均在**配置加载期**由 Computer 检出，属 **Computer 本地配置诊断**（日志 / 本地 UI），**不进协议错误码**、不由任何 `client:*` 事件触发（对齐 SKILL「物化失败 / 孤儿 / 跨 source 冲突不进协议错误码」先例）。配置人员据此修正配置：

| 诊断 | 触发 | 处置 |
|------|------|------|
| 重复 `bundle_id` | 两个及以上 Server 解析出相同 `bundle_id`（[no-double-open](#no-double-open)），仅启动配置顺序第一个 | 确需多实例 → 给冲突项指定**不同** `bundle_id`（如 `playwright` / `playwright_isolated`）|
| 非法 `bundle_id` | 显式传入含 `.` / 含 `__` / 字符集越界，或[缺省生成](#bundleid-缺省生成)极端输入后仍非法 | 修正为合规 `bundle_id`；**省略** `bundle_id` 不算错误（触发缺省生成）|
| `exposed_tool_name` 撞名 | **同一** `bundle_id` 内两个工具经 `alias` 产出相同 `exposed_tool_name` | 修正 `tool_meta` 的 `alias`（跨 `bundle_id` 不会撞，无需处理）|

> 运行期例外：`client:tool_call` 的 `tool_name` 在 [ExposedToolMapping](#exposedtoolmapping) 未命中，属客户端运行期错误，走协议错误码 [`4001`](error-handling.md#工具调用错误码)（非本地诊断）。

---

## 输入配置结构

输入配置用于定义 MCP Server 配置中的动态占位符。

### MCPServerInputBase

输入配置基类。

```python
class MCPServerInputBase(TypedDict):
    id: str             # 输入 ID
    description: str    # 描述
```

### MCPServerPromptStringInput

字符串输入类型。

```python
class MCPServerPromptStringInput(MCPServerInputBase):
    type: Literal["promptString"]
    default: NotRequired[str | None]        # 默认值
    password: NotRequired[bool | None]      # 是否为密码（隐藏输入）
```

### MCPServerPickStringInput

选择输入类型。

```python
class MCPServerPickStringInput(MCPServerInputBase):
    type: Literal["pickString"]
    options: list[str]                      # 可选项列表
    default: NotRequired[str | None]        # 默认值
```

### MCPServerCommandInput

命令输入类型（通过执行命令获取值）。

```python
class MCPServerCommandInput(MCPServerInputBase):
    type: Literal["command"]
    command: str                            # 要执行的命令
    args: NotRequired[dict[str, str] | None]  # 命令参数
```

### MCPServerInput

输入配置联合类型。

```python
MCPServerInput = MCPServerPromptStringInput | MCPServerPickStringInput | MCPServerCommandInput
```

---

## 类型别名

```python
from a2c_smcp.types import SERVER_NAME, TOOL_NAME, Attributes, AttributeValue

SERVER_NAME: TypeAlias = str        # MCP Server 名称（纯 display，人类可读，可碰撞，非身份）
BUNDLE_ID: TypeAlias = str          # MCP Server 唯一标识（BundleID）
TOOL_NAME: TypeAlias = str          # 工具原始名称
EXPOSED_TOOL_NAME: TypeAlias = str  # 聚合后暴露给 LLM 的工具名 {bundle_id}__{alias??原始名}
AttributeValue: TypeAlias = str | int | float | bool | None
Attributes: TypeAlias = dict[str, AttributeValue]
Desktop: TypeAlias = str        # 桌面内容（字符串形式）
```

---

## 参考

- 类型定义源码: `a2c_smcp/smcp.py`
- Pydantic 模型: `a2c_smcp/computer/mcp_clients/model.py`
- 通用类型: `a2c_smcp/types.py`
