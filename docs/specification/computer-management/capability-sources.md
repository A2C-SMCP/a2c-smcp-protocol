# Capability Sources

本文定义 Computer Management Plane 中多来源能力的统一归属、冲突、收敛、暴露与撤销规则。

Marketplace、plugin、用户本地配置、MCP Server resources 都可能贡献 MCP Server、tool policy、SKILL、input definition 或其它 managed capability。协议不规定这些内容如何下载、安装、落盘或缓存；协议规定它们进入 Computer 后如何标记来源、如何解决冲突、如何投影给 Agent，以及 source 被禁用或移除后如何撤销投影。

## 1. 管理范围

本模块管理：

- capability source kind 与 provenance。
- managed capability 的统一归属模型。
- marketplace / plugin / user / MCP resource 如何贡献能力。
- source precedence 与冲突处理边界。
- source disable / remove / disconnect 后的反向投影规则。
- 各来源最终进入 MCP Server、Tool Exposure、SKILL Exposure、Inputs and Secrets 等模块的收敛关系。

本模块不管理：

- marketplace 索引同步细节，见 [Marketplace](marketplace.md)。
- plugin manifest 格式和 installer 细节，见 [Plugin](plugin.md)。
- MCP Server runtime 启停，见 [MCP Server](mcp-server.md)。
- SKILL sandbox 和 `client:get_skill` 读取规则，见 [SKILL Exposure](skill-exposure.md)。
- 本地目录布局、包缓存、下载器、锁或文件格式。

## 2. Source Kinds

Computer Management Plane SHOULD track source provenance for every managed capability.

| Source kind | 示例 | 可贡献能力 |
|---|---|---|
| `user` | 用户本地配置或本地 drop-in SKILL | MCP Server config、SKILL、tool policy、input definition |
| `plugin:<plugin_id>` | 已安装 plugin | MCP Server config、SKILL、tool policy、input definition、marketplace source |
| `marketplace:<marketplace_id>` | marketplace 直接安装的 SKILL 或 package | installable plugin/SKILL metadata；安装后通常转为 plugin 或 SKILL source |
| `mcp:<server_name>` | MCP Server 通过 `resources/list` 暴露的 `skill://` | MCP source SKILL |

Source provenance 属于管理面诊断与收敛数据。Agent-facing 协议只暴露各通道已有的安全字段，例如 `A2CSkillRef.source`；不得为暴露 provenance 而泄露本地路径、凭据或安装日志。

`A2CSkillRef.source` 的 Agent-facing 取值仍以 [SKILL 通道 §SKILL 命名](../skill.md#1-skill-命名) 为准：

| 管理面来源 | Agent-facing `A2CSkillRef.source` |
|---|---|
| user drop-in / user installed SKILL | `user` |
| marketplace 直接安装的 SKILL | `marketplace:<repo>` |
| MCP Server `skill://` resource | `mcp:<normalized-server>` |
| plugin bundled SKILL from marketplace package | 通常投影为 `marketplace:<repo>`，并由管理面 diagnostics 记录 plugin provenance |
| plugin bundled SKILL not associated with marketplace | MAY 投影为 `plugin:<plugin_id>`，但 `plugin_id` MUST be non-sensitive and stable within the Computer |

Agent MUST treat `A2CSkillRef.source` as provenance metadata, not an authorization token or routing key. Computer MUST NOT expose plugin install paths, marketplace credentials or local package directories through this field.

## 3. Managed Capability

Managed capability 是 source 贡献给 Computer desired state 的能力描述。它不是 Agent-facing 协议对象本身，而是 reconcile 的输入。

| Capability | 最终管理模块 | Agent-facing 投影 |
|---|---|---|
| MCP Server config | [MCP Server](mcp-server.md) | `client:get_config`、tools/resources/Desktop/MCP source SKILL |
| Tool policy / metadata | [Tool Exposure](tool-exposure.md) | `client:get_tools`、`client:tool_call` |
| SKILL package / source | [SKILL Exposure](skill-exposure.md) | `client:get_skills`、`client:get_skill`、`client:get_blob` |
| Input definition / secret reference | [Inputs and Secrets](inputs-and-secrets.md) | `client:get_config` 的安全定义 |
| Marketplace source | [Marketplace](marketplace.md) | 通常无直接 Agent-facing 投影 |
| Plugin package | [Plugin](plugin.md) | 安装后转为 MCP/SKILL/tool/input 等投影 |

Source MUST NOT bypass the target module. For example, plugin MUST NOT directly publish a tool to `client:get_tools`; it contributes MCP/tool desired state, then Tool Exposure decides final visibility.

## 4. Source Contribution Flow

推荐收敛关系：

```text
marketplace sync
  -> installable packages
  -> plugin install or SKILL install
  -> managed capabilities
  -> reconcile target modules
  -> Agent-facing projection

plugin enable
  -> contributes MCP/SKILL/tool/input desired state
  -> reconcile target modules
  -> Agent-facing projection

user config
  -> contributes MCP/SKILL/tool/input desired state
  -> reconcile target modules
  -> Agent-facing projection

MCP Server running
  -> resources/list discovers skill://
  -> contributes mcp:<server_name> SKILL source
  -> SKILL Exposure stages/exposes/hides/orphans
  -> client:get_skills projection
```

This flow is SDK guidance. The normative requirement is that final Agent-facing projection MUST satisfy each target module's visibility, safety and conflict rules.

## 5. Conflict Handling

Multiple sources can contribute conflicting capabilities. Examples:

- user config and plugin both define MCP Server `browser`。
- plugin A and plugin B define the same tool alias。
- user SKILL and plugin SKILL synthesize the same name。
- MCP source SKILL and marketplace SKILL conflict by Agent-facing name。
- plugin-provided forbidden policy conflicts with user-provided enable policy。

Conflicted capabilities MUST NOT be exposed as available unless the conflict is resolved.

Computer Management Plane MUST use one of the following strategies:

1. Apply a documented source precedence policy.
2. Mark conflicting capabilities as `conflicted` / `invalid`.
3. Require explicit trusted-local user resolution.
4. Reject the management operation with a conflict error.

Computer MUST NOT resolve conflicts randomly or by nondeterministic iteration order.

SDK SHOULD document its source precedence policy. User-authored local policy SHOULD override plugin-provided policy unless the deployment defines a stricter organization policy.

The protocol does not mandate a universal precedence order. The conformance requirement is the observable result:

1. A conflicted capability MUST NOT appear as available in `client:get_tools`, `client:get_skills`, `client:get_desktop`, `client:get_resources` or `client:get_config` unless the conflict has been resolved by a documented deterministic policy or trusted-local user decision.
2. A conflicted tool name MUST NOT randomly route `client:tool_call` to different MCP Servers.
3. A conflicted SKILL name MUST NOT appear in `client:get_skills` with ambiguous `name` identity.
4. Conflict diagnostics MAY remain management-only and MUST NOT leak local paths, source credentials or install logs into Agent-facing responses.

## 6. Source Disable / Remove / Disconnect

When a source is disabled, removed, disconnected or becomes invalid, Computer MUST reconcile all capabilities contributed by that source.

| Source event | Required effect |
|---|---|
| plugin disabled | plugin-contributed MCP/SKILL/tool/input capabilities MUST become invisible or unavailable |
| plugin removed | plugin-contributed capabilities MUST be removed from subsequent projection |
| marketplace removed | installable index disappears; installed plugin/SKILL handling follows documented policy |
| MCP Server stopped/disabled/removed | tools/resources/Desktop from that server MUST be unavailable; `mcp:<server>` SKILLs MUST be hidden/orphaned/unavailable |
| user SKILL hidden/removed | that user source SKILL MUST disappear from `client:get_skills` |
| source policy rejected | contributed capabilities MUST NOT be exposed as available |

Removing a source MUST NOT delete unrelated capabilities from other sources, even if they share similar names, unless the documented conflict/precedence policy explicitly ties them together.

## 7. MCP Resource SKILL

When an enabled and running MCP Server exposes `skill://` resources through `resources/list`, Computer SHOULD treat them as `mcp:<server_name>` SKILL source contributions.

The lifecycle of MCP source SKILL is bound to the contributing MCP Server:

1. Server running and still exposing the SKILL -> SKILL MAY be staged and exposed according to SKILL Exposure policy.
2. Server stopped / disabled / removed -> contributed SKILL MUST NOT remain visible in `client:get_skills`.
3. Server disconnected temporarily -> contributed SKILL SHOULD be treated as orphaned or unavailable according to documented policy.
4. Server reconnects and still exposes the SKILL -> SKILL MAY recover and reappear after reconcile.
5. Server no longer exposes the SKILL -> SKILL MUST become hidden/orphaned/removed according to documented policy.

SKILL name lexer, staging, sandbox and `client:get_skill` errors remain governed by [SKILL Exposure](skill-exposure.md) and [SKILL 通道](../skill.md).

## 8. Agent-Facing Safety

Source provenance and diagnostics MUST NOT leak secrets or local internals to Agent-facing responses. In particular, Computer MUST NOT expose:

- marketplace credentials。
- plugin install logs。
- local package paths。
- secret values or env file contents。
- stack traces or internal cache metadata。

If source provenance is exposed through an existing safe protocol field, such as `A2CSkillRef.source`, it MUST use non-sensitive identifiers.
