# MCP 审批门对齐指南（SDK 非规范性共同依据）

> **定位**：MCP Server 审批门（approval gate）是 **SDK 自留地**——协议规范（specification/）不定义本地 settings 形态，仅在 [runtime-contract §5 item 10](../specification/computer-management/runtime-contract.md) 规定两套开关正交等硬约束。但双 SDK（python-sdk / rust-sdk）必须行为一致，故以本指南作为**共同对齐锚点**（替代此前各 SDK 引用自家私有设计文档的做法）。本文非 conformance 要求，第三方实现 MAY 不提供审批门；一旦提供，SHOULD 按本文对齐。

语义整体对标 Claude Code settings（`deniedMcpServers` / `allowedMcpServers` / `disabledMcpjsonServers` / `enabledMcpjsonServers` / `enableAllProjectMcpServers`），键语义按 A2C 身份模型调整如下。

## 1. 名单键 = `bundle_id`

四个名单数组（denied / allowed / disabledMcpjson / enabledMcpjson）的元素**一律为 `bundle_id`**（解析后运行期身份），不是 display name：

- **为什么**：按 name 授予信任会让「同名两条 server 共用一份审批」——你批准了 plugin 带的 `filesystem`，你自己那个恰好也叫 `filesystem` 的 server 自动免批准（真实信任泄漏）。bundle_id 键与 `get_config.servers` key、工具前缀 `{bundle_id}__`、错误码 `meta.mcp_server` 同一身份空间，零桥接。
- **hash-fallback 形态的免费收益**：bundle_id 为连接身份摘要形态时，改连接参数 ⇒ bundle_id 变 ⇒ 旧审批自然失效 ⇒ TOFU 语义。

## 2. 档位表（顺序即优先级，先到先决）

审批门只对**声明的 server**（mcp.json 各 scope 条目）判定；输入为 `(bundle_id, settings, trusted_origin)`：

| 档 | 判据 | 结果 |
|---|------|------|
| 1 | `deniedMcpServers` 含该 bundle_id（企业拒绝名单） | `DISABLED` |
| 2 | `allowedMcpServers` 非空且不含该 bundle_id（企业白名单） | `DISABLED` |
| 3 | `disabledMcpjsonServers` 含该 bundle_id（disabled 优先于 enabled） | `DISABLED` |
| 4 | `trusted_origin`（user / flag / policy scope 声明） | `ENABLED` |
| 5 | `enabledMcpjsonServers` 含该 bundle_id | `ENABLED` |
| 6 | `enableAllProjectMcpServers == true` | `ENABLED` |
| 7 | 否则（工作区共享且未决） | `PENDING`（弹批准框） |

!!! danger "历史档位「bundled 名集免批准」已删除，MUST NOT 以任何形状复活"

    旧实现在档 3 与 4 之间存在「`bundled.contains(name)` → ENABLED」档位。它是安全缺陷：真正的 plugin bundled server **从不进入** mcp.json 解析层（bundled 走 enable→mount，不落 mcp.json），因此该档**唯一可达路径**是「project/local 声明的 server 借用了某已装 plugin 的 server 名」——即 100% 借名跳过批准门（攻击者只需猜中受害者装过的任一插件的 server 名）。

    - **plugin 声明的 server MUST 不进入审批门迭代**——在迭代层过滤（`origin == plugin` 的条目不进门），**禁止**写成门内新档位（「进门后豁免」形状即旧档位复发，即便判据换成 origin 也重新违反 item 10「两套开关分别应用」）。其可信性由 install ∧ enable 门保证（[runtime-contract §2.5](../specification/computer-management/runtime-contract.md)）。
    - **审批门实现 MUST NOT 依赖物化账本 / bundled 名集**。
    - **可验收信号**：门函数签名不含 `bundled` 入参；代码库中不存在「读账本聚合 bundled 名集」的函数（如 `bundled_mcp_server_names()`）——「函数不存在」比「文档说别用」可靠。

## 3. settings 校验 fail-fast

加载 settings 时 MUST 校验四个名单数组的每个条目是合法 `bundle_id`；不合法条目进入既有 settings 校验错误通道（响亮失败，不静默忽略），报错信息 SHOULD 附带提示该 name 对应的 bundle_id：

```
❌ policy/settings.json
   deniedMcpServers[0]="my.server" 不是合法 bundle_id（含 '.'）
   提示: 该 server 的 bundle_id 为 "my_server"
```

这把「黑名单静默不生效 = 安全事故」变成响亮失败。policy 是企业下发的，用户本地改不了——但至少可见、可反馈给 admin。

## 4. 批准框 UX：name 与 bundle_id 双显示

`PENDING` 弹框 MUST 同时显示 display name（给人看）与 bundle_id（消歧 + 供日后手写 policy），批准写入的是 bundle_id：

```
╔══════════════════════════╗
║  发现新的 MCP Server      ║
║    filesystem            ║  ← name
║    bundle_a3f9c2e1       ║  ← bundle_id
║    npx @mcp/fs           ║
║  信任? [y]es [n]o [a]ll   ║
╚══════════════════════════╝
         ↓ y
enabledMcpjsonServers: ["bundle_a3f9c2e1"]
```

理由：同名两条 server 分别弹框时，只显示 name 会出现两个一模一样的框，用户分不清在批哪一个。

## 5. 写入面守卫（与 [runtime-contract §2.5](../specification/computer-management/runtime-contract.md) 优先序一致）

- **upsert（写 mcp.json）MUST NOT 因「同 bundle_id 已由 plugin 提供」而拒写**——用户在 user scope 声明同 bundle_id 正是优先序赋予的覆盖权（user > plugin 声明）。SDK MAY 提示「该 bundle_id 已由 plugin `<x>` 提供，你的声明将覆盖它」。
- **remove 守卫按 `origin` 判定，不按账本名集**：`origin == plugin ∧ 无用户侧声明` ⇒ 提示改用 `plugin uninstall`；用户侧存在声明 ⇒ 放行（删的是用户自己那条声明，plugin 基线保留）。

## 6. 双端一致性

本指南所有判定为**纯函数**（settings + origin → status），SHOULD 以共享测试向量对拍（姿态同 [bundle_id 一致性向量](../specification/computer-management/conformance-tests.md)）；夹具 MUST 遵循「display name 与 bundle_id 取值分叉」条款。
