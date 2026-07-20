# Computer 管理面一致性测试

本文定义 Computer Management Plane 的 SDK conformance checklist。测试应验证公开 SDK 结果、公开事件、wire 行为、错误分类和安全边界；不得检查私有 registry、缓存、锁、任务图、目录布局或语言专属类型。

## 1. 测试层级

| 层级 | 测试对象 | 必需观察点 |
|---|---|---|
| 协议投影 | 通过 SMCP Server 和 Agent 运行的 Computer | `client:*` responses、`server:update_*`、`notify:*`、flat `ErrorPayload` |
| Runtime contract | 公开 SDK runtime object | lifecycle state、public diagnostics、public errors、final projection |
| Fixture 对齐 | 共享 JSON config fixtures | 跨 SDK 的等价 runtime intent |
| 安全 | 公开 SDK 和 Agent-facing protocol | 无 secret/path leakage，sandbox 与 blob boundaries 正确 |

## 2. 共享 Fixtures

一致性测试套件 SHOULD 在各 SDK 间使用同一批 JSON fixtures。具体磁盘位置由 SDK 自行决定，但每个 SDK SHOULD 能加载等价于以下内容的 fixtures。

### 2.0 测试学硬条款（防「假绿」）

以下三条源自同一失效模式在两个 SDK 五处独立复发的教训，MUST 遵守：

1. **夹具身份分叉**：一致性夹具中 display `name` 与 `bundle_id` **MUST 取值分叉**（如 name `"stdio srv (display)"` → bundle_id `stdio_srv_display`）。缺省派生下 `bundle_id == normalize(name)`，二者恰好重合会把所有身份裂缝盖住——「按 name 取键」与「按 bundle_id 取键」的实现错误在此类夹具下**双双通过**（零鉴别力）。本文其余章节的示例夹具若未分叉，仅为行文简洁，实现 MUST 分叉。
2. **异 id 同名共存向量**：「显式不同 `bundleId` + 相同 display name 的 server 合法共存」场景 **MUST 有双端对拍向量**，覆盖：两条均保留（去重不塌陷）、分组/归属/审批各自独立、寻址歧义按 [sdk-api-guidance §5.1](sdk-api-guidance.md) 报错。既有 bundle_id 一致性向量只对拍**生成算法**；寻址行为是缺陷高发的另一半，MUST 单独对拍。
3. **真实构造路径**：涉及 Computer 聚合状态的契约测试（如 `client:get_config` 投影）**MUST 至少一条用例走真实构造路径**（真实 Computer 构造 + 运行期挂载，含「构造期集合为空、server 全部运行期挂入」的形态），不得全部依赖桩——桩会把生产中恒假的前提固化为真（桩里塞满 server，而真实 CLI 构造期集合恒空）。

### 2.1 Minimal Runtime

```json
{
  "name": "computer-a",
  "mcp_servers": [],
  "inputs": [],
  "installedPlugins": [],
  "enabledPlugins": {},
  "marketplaces": {}
}
```

期望：

- create 成功；
- start 到达 `started` 或等价状态；
- `client:get_config` 返回空 `servers`；
- `client:get_tools` 返回空 `tools`；
- shutdown 释放 resources。

### 2.2 One Stdio MCP Server

```json
{
  "name": "computer-a",
  "mcp_servers": [
    {
      "name": "echo",
      "type": "stdio",
      "disabled": false,
      "forbidden_tools": [],
      "tool_meta": {},
      "server_parameters": {
        "command": "fixture-echo-server",
        "args": [],
        "env": null,
        "cwd": null
      }
    }
  ],
  "inputs": []
}
```

期望：

- enabled server 出现在 `client:get_config` 中；
- fixture server 暴露的 tools 出现在 `client:get_tools` 中；
- `client:tool_call` 返回 MCP `CallToolResult`；
- 移除或禁用 server 后，后续 projection 中移除对应 tools。

### 2.3 Disabled And Forbidden Tools

```json
{
  "name": "computer-a",
  "mcp_servers": [
    {
      "name": "tools",
      "type": "stdio",
      "disabled": false,
      "forbidden_tools": ["dangerous_delete"],
      "tool_meta": {
        "safe_read": { "tags": ["read"], "auto_apply": true }
      }
    }
  ]
}
```

期望：

- forbidden tool 不出现在 `client:get_tools` 中；
- forbidden tool 不能被成功执行；
- `safe_read` metadata 以 JSON 字符串出现在 `meta["a2c_tool_meta"]` 下。

### 2.4 Marketplace Plugin

```json
{
  "name": "computer-a",
  "marketplaces": {
    "acme": {
      "source": { "type": "git", "url": "file:///fixtures/acme-marketplace" },
      "autoUpdate": false
    }
  },
  "installedPlugins": ["audit@acme"],
  "enabledPlugins": {
    "audit@acme": true
  }
}
```

期望（`installed_enabled`，如上 fixture）：

- startup reconcile 是 additive；
- enabled plugin SKILLs 出现在 `client:get_skills` 中；
- plugin-contributed MCP servers 通过常规 config/tool projection 出现；
- 禁用 `audit@acme`（`enabledPlugins: {"audit@acme": false}`）会移除或隐藏其贡献的 capabilities，但保留其 installation；
- 仅移除 declaration 不会删除已物化 marketplace，直到显式 prune/gc；
- **重启恢复**：以相同 `home` 重建 runtime、执行 boot/reconcile 后，`audit@acme` 的 bundled MCP servers、bundled SKILLs 及其派生 MCP-source SKILLs 重新出现，且无需调用方在内存中记忆归属；
- **Scope 隔离**：plugin 全局安装、仅在某 scope 启用时，未启用的 scope 的活跃集不出现该 plugin 贡献的能力。

期望（`installed_disabled`，把 fixture 改为 `"installedPlugins": ["audit@acme"]` 且 `enabledPlugins` 不含 `audit@acme`）：

- `audit@acme` 出现在已安装列表（installed），但其 SKILLs **不**出现在 `client:get_skills`、bundled MCP server **不**出现在活跃 config/tool projection——即 `install` ≠ activate；
- **重启恢复保持惰性**：以相同 `home` 重建、boot/reconcile 后，`audit@acme` 仍在已安装列表且仍**不**投影任何能力（不会因重启被激活）；
- 随后 `enable`（`enabledPlugins: {"audit@acme": true}`）后，其 SKILLs 与 bundled server **一并**出现；若 enable 期间 bundled server 挂载失败，MUST 回滚到 `installed_disabled`（不留「skill 亮、server 未挂」的半态）。

### 2.5 Secret Inputs

```json
{
  "name": "computer-a",
  "inputs": [
    {
      "type": "promptString",
      "id": "api_token",
      "description": "API token",
      "password": true
    }
  ],
  "mcp_servers": [
    {
      "name": "secret-server",
      "type": "stdio",
      "server_parameters": {
        "command": "fixture-secret-server",
        "args": ["${input:api_token}"],
        "env": { "TOKEN": "${input:api_token}" },
        "cwd": null
      }
    }
  ]
}
```

期望：

- resolved token 只在本地使用；
- `client:get_config` 不暴露 resolved token；
- Agent 可见的 errors 和 diagnostics 不包含 token；
- 具有相同 bare id 的 plugin-scoped input fixtures 不会串值。

## 3. Runtime Contract Checklist

### 3.1 Create From Config

- 给定合法 minimal fixture，创建 runtime 成功且不需要网络访问。
- 给定非法 JSON shape，SDK 返回公开 `validation` error。
- 给定非法 plugin id shape，SDK 返回公开 `validation` error。
- 创建 runtime 不会启动 MCP tool execution。
- 创建 runtime 不会发送 `server:update_*`。

### 3.2 Start

- `start` 为合法 config 初始化本地 projection。
- 当一个 MCP Server 启动失败时，startup 进入 `degraded` 或返回 partial diagnostics，且不会把该 server 的 tools 暴露为可用。
- Startup 不会在 public diagnostics 中暴露 secret values。
- 重复 `start` 是幂等的，或返回明确 lifecycle conflict。

### 3.3 Connect And Join

- `connect` 在 URL query 中发送 `a2c_version`。
- `connect` 的 `auth` 仅承载 caller-provided business auth fields，不含 `role`。
- auth payload 中不包含 MCP credentials 和 `.skillenv` 内容。
- Join Office 使用 `server:join_office`，并携带 `role = "computer"`（角色即在此声明）和配置的 Computer name。
- Protocol version mismatch 被分类为 `protocol_version`。
- Auth failure 被分类为 `auth`。

### 3.4 Sync Config

- 通过 `sync_config` 添加 MCP Server 后，其 tools 在成功后可见。
- 通过 `sync_config` 禁用 MCP Server 后，其 tools 从 `client:get_tools` 中移除。
- 通过 `sync_config` 移除 MCP Server 后，对该 server 调用 `client:get_resources` 返回 `4014`。
- 修改 tool metadata 会更新 `SMCPTool.meta`。
- 修改 SKILL sources 会更新 `client:get_skills`。
- 如果已加入 Office，每个改变 projection 的 sync 会发送相关 `server:update_*` request，或发送等价的合并后集合。
- Partial failure 不会留下可见的歧义重复 `tool_name` 路由。

### 3.5 Disconnect、Stop、Shutdown

- `disconnect` 结束 Socket.IO connection，且不删除 durable desired state。
- `disconnect` 后，本地管理变更不会向之前的 Office 发送 update events。
- `stop` 在完成后阻止新的 Agent-facing service activity。
- `shutdown` 在需要时断开连接，停止 owned MCP activity，并停止 watchers/timers。
- `shutdown` 后，stale callbacks 不会发送 `server:update_*`。
- 重复 `shutdown` 是幂等的，或返回明确 lifecycle state result。

## 4. Protocol Projection Checklist

### 4.1 Config

- `client:get_config` 返回当前安全的 `servers` 和 `inputs`。
- Disabled servers 要么不存在，要么按既有 config semantics 明确为非 active；它们不暴露 callable tools。
- Secret values、OAuth tokens、API keys、`.skillenv` 内容和本地 credential file contents 均不存在。
- Unknown management diagnostics 不存在。

### 4.2 Tools

- `client:get_tools` 只返回 enabled、non-forbidden 且 uniquely routable 的 tools。
- 存在复杂 A2C metadata 时，`a2c_tool_meta` 是 JSON 字符串。
- Duplicate tool names 在暴露前通过 alias、disable/reject 或其它 deterministic policy 解决。
- 对 removed/disabled/forbidden tools 的 `client:tool_call` 不能成功。

### 4.3 Resources

- 带 `resources` capability 的已知 MCP Server 返回透明的 `resources/list` page。
- 未知 `mcp_server` 返回 flat `ErrorPayload`，且 `code = 4014`。
- 缺少 `resources` capability 的 server 返回 flat `ErrorPayload`，且 `code = 4015`。
- Response 不按 scheme、`_meta`、annotations 或 content 过滤。

### 4.4 SKILL

- `client:get_skills` 返回 active refs，并排除 orphan/removed/disabled plugin refs。
- 必选字段 `name`、`source`、`path`、`description` 存在。
- `client:get_skill` 中的 invalid `name` 返回 `4016`。
- Missing/orphan/removed name 返回 `4014`。
- Traversal、absolute path、`.skillenv`、forbidden file 和 not-found `rel_path` 返回 `4017`。
- inline budget 内的 text 返回 `body`；binary 或 large text 返回 `blob_handle`；两者绝不同时存在。

### 4.5 Blob

- `client:get_blob` 将 handle 视为 opaque，并按 absolute offset 返回 chunks。
- Invalid handle 返回 `4018`，并带 `details.reason = "invalid_handle"` 或等价信息。
- handle mint 后 source 被移除，返回 `4018`，并带 `gone` 或等价信息。
- Out-of-range offset 返回 `4018`，并带 `range` 或等价信息。
- `total_size` 和 `sha256` 在一次 logical read 内保持稳定。
- Blob access 不能读取任意本地文件。

### 4.6 Desktop

- `client:get_desktop` 只返回 valid `window://` rendered entries。
- 精确 `window` filter 只返回匹配 URI 或空列表。
- Invalid/empty/unrenderable windows 被跳过。
- Management diagnostics 和 local paths 不会渲染进 Desktop content。

### 4.7 Cancellation And Timeout

- `server:tool_call_cancel` 保持 fire-and-forget；不需要 ack。
- Unknown 或 completed `req_id` 被 Computer 忽略，且不产生新协议错误。
- 成功取消时，原始 `client:tool_call` ack 返回 `CallToolResult(isError=true)`，且结果级 `meta.a2c_cancelled = true`。
- Timeout 返回 `CallToolResult(isError=true)`，并 SHOULD 包含结果级 `meta.a2c_timeout = true`。

### 4.8 上游授权错误 Surfacing（4006/4007）

MCP 上游授权失败的 surfacing 属协议投影硬约束（[error-handling.md → MCP 上游授权错误响应](../error-handling.md#mcp-上游授权错误响应)）：检测点归 SDK 自治，但结果与可观测判据双端 **MUST** 一致。

- Computer 判定上游失败**属授权类**（含 MCP 客户端库吞掉状态码、只给语义变体的情形，如 rmcp `AuthRequired`）后，`client:tool_call` 的 `CallToolResult` **MUST** 携带 `meta.error_code` ∈ {4006, 4007}、`isError=true`、`meta.mcp_server` = 该 server 的 bundle_id；**MUST NOT** 降级为 `4003`、亦 **MUST NOT** 返回缺 `meta.error_code` 的 `isError=true` 通用失败结果（[降级语义](../error-handling.md#降级语义授权类失败的硬映射)）。
- 授权失败 **MUST NOT** 表现为调用挂起至超时；Computer **MUST** 在自身超时或 Agent 超时之前（取较早者）产出上述结果（[可观测判据](../error-handling.md#可观测判据禁止挂起至超时)）。

**真实传输四景对拍向量（双端 MUST 覆盖）+ 一景 rust-sdk 手写 SSE 补充（python-sdk 可 N/A）**（[`fixtures/auth_error_conformance_vectors.json`](../fixtures/auth_error_conformance_vectors.json)，源自 [Discussion #34](https://github.com/A2C-SMCP/a2c-smcp-protocol/discussions/34) 裁决）——双端 MUST 用真实 MCP server（initialize 放行、仅 `tools/call` 返指定状态）覆盖，禁止以合成错误对象充数（遵 [§2.0 测试学硬条款第 3 条](#20-测试学硬条款防假绿)）：

1. `403` → 4007（双端基线，状态码经 `error_for_status` 保留）
2. `401` 无 `WWW-Authenticate` → 4006（双端基线）
3. `401` **带** `WWW-Authenticate`（RFC 6750 §3 要求的 OAuth 合规标准应答）→ **4006** —— rmcp 此景短路 `AuthRequired` 丢状态码、修复前漏报，本景强制 SDK 用结构化判定（downcast 语义变体 / 拦截响应头）覆盖；修复后双端 MUST 翻转为 4006
4. `POST 200` + SSE 流内 `401` → **4006 且不挂起** —— rmcp/mcp-python 此景使响应永不到达，本景强制 Computer 在已观测到流内授权失败信号后自身兜底合成 4006；修复后双端 MUST 在自身/Agent 超时之前返回而非挂至超时

挂起判定用 time-box（`tokio::time::timeout` / `asyncio.wait_for`）区分「返结果」与「挂起」。rust-sdk 另有手写 SSE 客户端路径景（`sse_client.rs` 合成含 `"401"` 的 JSON-RPC error），python-sdk 无对应手写 SSE 路径可 N/A。

**范围外（OOS）**：① **握手阶段（initialize）返 401** 不在本向量——该路径在 rmcp 进 fatal lifecycle、不进 `tools/call` 分类，归属 server registration lifecycle 而非 surfacing；如未来需协议约束应另行立条。② [判定决策表](../error-handling.md#40064007-判定决策表) Row 4（Token 过期 + refresh 失败 → 4007）非 `tools/call` 请求-响应、Row 6（凭证存在但 scope 不足、上游无显式 401/403 → 4007）缺可稳定复现的真实上游构造——这两行的判定由 SDK 单元测试覆盖语义即可，不纳入真实传输向量。

## 5. Marketplace And Plugin Checklist

- Marketplace reconcile 会安装 missing declared marketplace sources。
- Source change 会在 reconcile 后替换旧 source projection。
- `autoUpdate` 或 explicit refresh 会更新 declared source。
- Undeclared materialized marketplaces 不会在 additive startup reconcile 期间被删除。
- Explicit prune 会移除 marketplace materialization，并注销其 active SKILLs。
- Plugin install 校验 `<plugin>@<marketplace>` shape。
- marketplace unknown 时，Plugin install 失败。
- Plugin install 对声明依赖的 MCP Server 按 `bundle_id` 依赖预检（数据源 = 运行期权威配置集）：同 `bundle_id` 已存在 → **提示「依赖已满足」并正常安装**（MUST NOT 拒绝）；display 同名、`bundle_id` 不同 → 正常安装（合法共存，MUST NOT 误拒）。
- 同一声明文件内两个 key 归一到同一 `bundle_id` → 注册边界 fail-fast（提示改名或显式 `bundleId`）。
- plugin 声明的 MCP Server 的 reinstall/enable 是幂等的。
- Plugin disable 会使贡献的 SKILLs/tools/MCP resources 不可见或不可调用。
- Plugin uninstall 按 §4.9.1 回收判据处理其声明依赖的 server：无其他 plugin 依赖 ∧ 非用户声明 → 回收；用户声明的同 `bundle_id` server 永不连坐；另一 plugin 仍依赖时保留、最后一个依赖者卸载时回收（无泄漏）。
- **回收判据 origin 向量**（[Discussion #32 裁决](https://github.com/A2C-SMCP/a2c-smcp-protocol/discussions/32)）：「非用户声明」MUST 评估在带 `origin` 的运行期权威配置集上（runtime-contract §2.5 第 5 条）。四景 MUST 双端对拍：① X 经 flag（`--mcp-config`）挂载（`origin=flag`）→ 卸载声明依赖 X 的 plugin **不回收** X；② X 经宿主构造入参挂载（`origin=embed`）→ 同上**不回收**；③ X 仅由 plugin 声明（`origin=plugin`、无其他 plugin 依赖）→ **回收**；④ 同 `bundle_id` 混源碰撞（plugin 声明 + flag 声明并存，flag > plugin）→ **不回收**。夹具遵 §2.0 name/bundle_id 分叉条款。
- uninstall 的停摘名单仅依赖账本自身字段（删除 installPath 树之后仍可精确停摘）。
- Plugin-scoped inputs 会在 plugin server config rendering 前注入。
- 命令式操作 config-first：`install` 写 `installedPlugins`（全局安装意图）、`enable`/`disable` 写 `enabledPlugins`（per-scope 启用意图）；物化账本只作为下游派生物出现，不被直接编辑。
- **install ≠ activate**：仅 `install`（未 `enable`）后，该 plugin 处于 `installed_disabled`——在已安装列表，但其 SKILLs **不**在 `client:get_skills`、bundled MCP server **不**在活跃 config/tool projection。
- **enable 原子激活**：`enable` 后 skills 与 bundled server 一并出现；enable 时 bundled server 挂载失败 MUST 回滚到 `installed_disabled`（不留半态）。
- 重启恢复（enabled）：install+enable 后以相同 `home` 重建 runtime，boot/reconcile 后 bundled MCP servers、bundled SKILLs、派生 MCP-source SKILLs 与归属元数据重新出现。
- 重启恢复（installed_disabled）：仅 `install`（未 `enable`）后以相同 `home` 重建，boot 后该 plugin 仍在已安装列表但保持惰性——不出现在活跃 skills/servers。
- disable/uninstall 后以相同 `home` 重建 runtime，boot/reconcile 不再恢复该 plugin 的 MCP servers、SKILLs 及其派生 MCP-source SKILLs。
- 给定 `{settings.json + .mcp.json + 已安装 plugin 目录}` fixture，boot 后的活跃 `{skills, servers}` 集合与来源标注与期望一致。
- 存储的 install 路径失效时，boot 由 `(marketplace, plugin, version)` 纯函数重算，恢复不受影响。

## 6. Security Checklist

- Agent 不能通过任何 `client:*` event 调用 management mutation。
- 包含 local paths 的 management errors 不会被复制进 Agent-facing `ErrorPayload.details`。
- Secret values 不会出现在 `client:get_config`、`client:get_tools`、`client:get_desktop`、`client:get_skill`、`client:get_blob`、update notifications 或 tool metadata 中。
- SKILL sandbox 防止 traversal、symlink escape 和 forbidden file access。
- Blob handle parsing 会重新执行 source authorization/boundary checks。
- Cleanup operations 拒绝删除 authorized Computer local boundary 之外的内容。
- Policy-rejected marketplace/plugin/source 不贡献任何 visible capability。

## 7. Cross-SDK Parity Matrix

每个 SDK SHOULD 报告以下项目的 pass/fail：

| 区域 | Python | Rust | TypeScript | 备注 |
|---|---|---|---|---|
| Config fixture parsing | 必需 | 必需 | 推荐 | 同一 fixture，等价 runtime intent |
| Lifecycle transitions | 必需 | 必需 | 推荐 | Public state 或 mapped diagnostics |
| Wire projection | 必需 | 必需 | 推荐 | 通过 test Server + Agent |
| Marketplace/plugin | feature 存在时必需 | feature 存在时必需 | 推荐 | 允许 feature-gated |
| Secret safety | 必需 | 必需 | 必需 | 不允许 feature gate |
| Shutdown cleanup | 必需 | 必需 | 推荐 | 只验证 public effects |

只有当 SDK 不声称具备 marketplace/plugin management capabilities 时，feature-gated SDK 才可以把 marketplace/plugin tests 标记为 not applicable。Protocol projection 和 secret safety tests 对任何 Computer SDK 都仍然是必需项。

## 8. 证据覆盖

当前 Python 和 Rust SDK 已经包含大多数 checklist 区域的证据：

| 区域 | Python tests/source | Rust tests/source |
|---|---|---|
| Computer lifecycle and tools | `tests/unit_tests/computer/*`、`tests/integration_tests/computer/*`、`a2c_smcp/computer/computer.py` | `crates/smcp-computer/tests/*`、`tests/v022_integration_matrix.rs`、`crates/smcp-computer/src/computer.rs` |
| Socket.IO Computer client | `a2c_smcp/computer/socketio/client.py` | `crates/smcp-computer/src/socketio_client.rs` |
| Settings and reconcile | `a2c_smcp/computer/settings/*`、`tests/unit_tests/computer/settings/*` | `crates/smcp-computer/src/settings/*` unit tests |
| SKILL/blob/Desktop | `tests/e2e/test_v02_skill_blob_e2e.py`、`tests/integration_tests/test_blob_transfer.py`、desktop tests | `tests/v022_integration_matrix.rs`、`crates/smcp-computer/tests/desktop_integration.rs`、blob/skill modules |

这些是证据指针，不是未来 SDK 的强制文件路径。

## 9. 兼容性

兼容性标签：**Runtime-contract + SDK conformance**。

这些测试不需要改变 wire schema。它们可能暴露 SDK 行为缺口，这些缺口应作为 SDK conformance work 修复。
