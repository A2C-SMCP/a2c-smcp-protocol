# SKILL Exposure Management

本文定义管理面如何控制 SKILL 的安装、物化、显隐、孤儿状态与 Agent-facing 投影。

## 1. 管理范围

本模块管理：

- SKILL source：`user`、`mcp`、`marketplace`、`plugin-provided`。
- 管理面状态：installed / staged / exposed / hidden / orphaned / invalid / removed。
- list / refresh / install / expose / hide / remove / diagnostics。
- SKILL name 冲突、frontmatter 诊断和 sandbox 投影。
- `client:get_skills`、`client:get_skill`、`client:get_blob` 的可见结果。
- 所有 SKILL source 最终进入统一 SKILL registry 的规则。

本模块不管理：

- marketplace source 同步，见 [Marketplace](marketplace.md)。
- plugin 安装与启停，见 [Plugin](plugin.md)。
- source provenance、冲突和撤销的通用规则，见 [Capability Sources](capability-sources.md)。
- Blob 分块传输细节，见 [通用二进制传输](../blob-transfer.md)。

## 2. Source 与状态

| State | 含义 | Agent-facing 投影 |
|---|---|---|
| `installed` | 管理面知道该 SKILL source 或包 | 不一定可见 |
| `staged` | 已物化到 Computer 可读包结构 | 可进入曝光判断 |
| `exposed` | 允许 Agent 发现和读取 | 出现在 `client:get_skills` |
| `hidden` | 本地保留但不对 Agent 可见 | 不出现在 `client:get_skills` |
| `orphaned` | source 已消失或断开 | 不出现在 `client:get_skills` |
| `invalid` | name/frontmatter/package/sandbox 校验失败 | 不出现在 `client:get_skills` |
| `removed` | 已删除或注销 | `client:get_skill` 返回 not found 语义 |

隐藏、安装失败、frontmatter 错误、source orphan 等管理面状态 MAY 对管理员可见，但 MUST NOT 通过 `client:get_skills` 暴露为可用 SKILL。

## 3. Operations

| 能力 | 语义 | 完成后的协议投影 |
|---|---|---|
| list skills | 列出所有管理面 SKILL，含 hidden/orphan/error 状态 | 不要求通知 |
| refresh skills | 重新扫描 source 并 reconcile Registry | 变化时 `server:update_skills` |
| install user skill | 从本地包或目录安装 user source SKILL | 活跃时进入 `client:get_skills` |
| expose skill | 允许 SKILL 对 Agent 可见 | `client:get_skills` 返回该 SKILL |
| hide skill | 让 SKILL 对 Agent 不可见但可保留本地安装 | `client:get_skills` 不返回该 SKILL |
| remove skill | 删除或注销 SKILL | 后续 `client:get_skill` 返回 `4014` |
| read skill diagnostics | 返回 staging / frontmatter / sandbox 诊断 | 不进入 Agent-facing 协议 |

## 4. Agent-Facing Rules

`client:get_skills` MUST 只返回 active exposed SKILL。`client:get_skill` 对非法 name、not found、sandbox 拒绝和过大资源的行为仍以 [SKILL 通道](../skill.md) 为准。

SKILL 集合、frontmatter、可见性或包内容变化 SHOULD 触发 `server:update_skills`。

Agent-facing source and identity MUST remain stable across management implementation choices:

1. `A2CSkillRef.name` MUST follow [SKILL 通道 §SKILL 命名](../skill.md#1-skill-命名).
2. `A2CSkillRef.source` MUST be non-sensitive provenance as defined by [Capability Sources §Source Kinds](capability-sources.md#2-source-kinds).
3. `client:get_skill` MUST NOT reveal whether hidden, orphaned, invalid or policy-rejected SKILLs exist. For a legal but unavailable name it MUST use the same not-found semantics as an unregistered name.
4. `client:get_skill` and `client:get_blob` MUST continue to enforce the SKILL sandbox after management changes. A handle or name that was valid before hide/remove/orphan MAY become inaccessible and then follows the existing `4014` / `4018` rules.

## 5. Source Convergence

不管 SKILL 来自 user、marketplace、plugin 还是 MCP `skill://` resource，Computer MUST 通过同一套 SKILL Exposure 规则决定它是否进入 `client:get_skills`。

Conflicted SKILL names MUST NOT be exposed as available unless resolved by documented source precedence or trusted-local user decision. Source disabled / removed / disconnected 后，该 source 贡献的 SKILL MUST 按 [Capability Sources](capability-sources.md) 撤销或标记 orphan/hidden/invalid。

Plugin-provided SKILLs are not a separate Agent-facing channel. They enter the same registry and are read through the same `client:get_skills` / `client:get_skill` / `client:get_blob` events as user, marketplace and MCP source SKILLs. Plugin install layout, staging directory and cleanup timing are SDK guidance.
