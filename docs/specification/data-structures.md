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

**说明**: 当 Computer 管理多个 MCP Server 时，可能存在工具名称冲突。此时可通过 `meta` 中的 `alias` 字段设置别名进行区分。

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
    # 工具别名，用于解决不同 Server 下的工具重名冲突

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

## 房间管理结构

### EnterOfficeReq

加入房间请求。

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
```

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

配置更新请求。同时被 Desktop 更新事件（`server:update_desktop` / `notify:update_desktop`）复用。

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
    servers: dict[str, MCPServerConfig]                 # MCP Server 配置映射
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
    window: NotRequired[str]        # 可选：指定获取的 WindowURI
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
window://com.example.browser/main?priority=80

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

## MCP Server 配置结构

### BaseMCPServerConfig

MCP Server 配置基类。

```python
class BaseMCPServerConfig(TypedDict):
    name: str
    # MCP Server 名称

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

SERVER_NAME: TypeAlias = str    # MCP Server 名称
TOOL_NAME: TypeAlias = str      # 工具名称
AttributeValue: TypeAlias = str | int | float | bool | None
Attributes: TypeAlias = dict[str, AttributeValue]
Desktop: TypeAlias = str        # 桌面内容（字符串形式）
```

---

## 参考

- 类型定义源码: `a2c_smcp/smcp.py`
- Pydantic 模型: `a2c_smcp/computer/mcp_clients/model.py`
- 通用类型: `a2c_smcp/types.py`
