# Marketplace Management

本文定义管理面如何配置和同步 marketplace source。Marketplace 本身通常不直接暴露给 Agent；其安装结果会投影为 plugin、SKILL、MCP Server 或其它 Computer capability。

## 1. 管理范围

本模块管理：

- marketplace identity：id、name、url/ref 或其它 source locator。
- marketplace 状态：configured / syncing / available / unavailable / auth_failed / removed。
- list / add / remove / sync / search / status。
- marketplace 认证、索引缓存、版本发现和兼容性诊断的边界。
- marketplace 作为 installable source 的 provenance 边界。

本模块不管理：

- 已安装 plugin 的 enable/disable/remove，见 [Plugin](plugin.md)。
- 多来源能力贡献与冲突规则，见 [Capability Sources](capability-sources.md)。
- SKILL 是否 exposed，见 [SKILL Exposure](skill-exposure.md)。

## 2. 状态

| State | 含义 | Agent-facing 投影 |
|---|---|---|
| `configured` | source 已登记 | 无直接投影 |
| `syncing` | 正在刷新索引 | 无直接投影 |
| `available` | 索引可用 | 无直接投影 |
| `unavailable` | 网络、格式或其它失败 | 无直接投影 |
| `auth_failed` | 凭据失效或无权限 | 无直接投影 |
| `removed` | source 已移除 | 取决于已安装对象处理策略 |

## 3. Operations

| 能力 | 语义 | 完成后的协议投影 |
|---|---|---|
| list marketplaces | 列出已配置 marketplace source | 不要求通知 |
| add marketplace | 新增 marketplace source | 通常不直接通知；安装/同步结果触发 |
| remove marketplace | 移除 marketplace source，并按策略处理已安装 plugin/SKILL | 受影响能力变化时发送 update |
| sync marketplace | 拉取或刷新 marketplace 索引 | 若安装集合不变，不要求通知 |
| search marketplace | 查询可安装 plugin/SKILL | 不进入 Agent-facing 协议 |
| get marketplace status | 查看认证、同步和索引诊断 | 不进入 Agent-facing 协议 |

## 4. 安装结果投影

Marketplace sync 本身不要求触发 Agent-facing update。Marketplace 通常只改变 installable package index；只有当 sync、install、update 或 remove 改变已安装 plugin/SKILL/MCP 能力时，Computer SHOULD 按 [Reconcile and Notifications](reconcile-and-notifications.md) 发送对应通知。

Marketplace-discovered packages MUST NOT bypass target modules. 安装 plugin 后，其贡献能力按 [Plugin](plugin.md) 与 [Capability Sources](capability-sources.md) 收敛；直接安装 SKILL 时，其 SKILL source MUST 进入 [SKILL Exposure](skill-exposure.md)。

Marketplace 凭据、索引内容、下载日志和错误详情属于管理面诊断，MUST NOT 自动进入 Agent-facing 响应。
