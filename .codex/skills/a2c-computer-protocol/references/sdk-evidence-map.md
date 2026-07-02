# SDK 证据地图

从 SDK 中抽取 Computer 行为时使用本参考。

## 默认仓库

| 角色 | 默认路径 |
|---|---|
| 协议 | `/Users/huruize/VSCodeProject/a2c-smcp-protocol` |
| Python SDK | `/Users/huruize/VSCodeProject/python-sdk` |
| Rust SDK | `/Users/huruize/VSCodeProject/rust-sdk` |

## 需要检查的 Python 文件

| 领域 | 路径 |
|---|---|
| Computer core | `a2c_smcp/computer/computer.py`, `a2c_smcp/computer/base.py` |
| Socket.IO handlers | `a2c_smcp/computer/socketio/client.py` |
| MCP manager | `a2c_smcp/computer/mcp_clients/manager.py`, `a2c_smcp/computer/mcp_clients/model.py` |
| Inputs | `a2c_smcp/computer/inputs/*.py` |
| Skills | `a2c_smcp/computer/skills/*.py` |
| Blob | `a2c_smcp/computer/blob/*.py` |
| Desktop | `a2c_smcp/computer/desktop/*.py`, `a2c_smcp/utils/window_uri.py` |
| Settings | `a2c_smcp/computer/settings/*.py` |
| Tests | `tests/unit_tests/computer/**`, `tests/integration_tests/computer/**`, `tests/e2e/computer/**` |

## 需要检查的 Rust 文件

| 领域 | 路径 |
|---|---|
| Computer core | `crates/smcp-computer/src/computer.rs`, `crates/smcp-computer/src/lib.rs` |
| Socket.IO handlers | `crates/smcp-computer/src/socketio_client.rs` |
| MCP manager | `crates/smcp-computer/src/mcp_clients/manager.rs`, `crates/smcp-computer/src/mcp_clients/model.rs` |
| Inputs | `crates/smcp-computer/src/inputs/*.rs` |
| Skills | `crates/smcp-computer/src/skills/*.rs` |
| Blob | `crates/smcp-computer/src/blob/*.rs` |
| Desktop | `crates/smcp-computer/src/desktop/*.rs` |
| Settings | `crates/smcp-computer/src/settings/*.rs` |
| Tests | `crates/smcp-computer/tests/**`, `tests/**computer**.rs` |

## 证据表格式

起草协议文本前使用这张表：

| 主题 | 当前协议文档 | Python 行为 | Rust 行为 | 是否共享 | 是否适合进入协议 | 开放问题 |
|---|---|---|---|---|---|---|
| 示例：取消未知 `req_id` | `events.md`, `error-handling.md` | no-op/false | no-op/false | 是 | 如果 Agent 能观察到，协议可以 MAY 指定幂等 no-op | no-op 是否应成为规范要求？ |

## 证据标准

- 判断实际行为时，优先看测试而不是注释。
- 优先看 public handler 行为，而不是 private helper 行为。
- 只有两个 SDK 实现了等价的外部语义时，才将行为标记为 "shared"。
- 当某个 SDK 缺少行为时，即使协议已经要求，也标记为 "missing"。
- 当行为只影响本地结构、缓存布局、日志、CLI UX 或 helper API 时，标记为 "implementation detail"。

## 常用搜索模式

在各 SDK 根目录运行：

```bash
rg "client:get_|server:update_|notify:update_|tool_call_cancel|get_blob|get_skill|get_desktop|get_resources"
rg "a2c_blob_handle|a2c_cancelled|a2c_timeout|ErrorPayload|4016|4017|4018|4014|4015"
rg "window://|skill://|fullscreen|priority|audience|BlobHandle|SkillRegistry"
rg "add_or_update_server|remove_server|forbidden_tools|alias|auto_reconnect|health"
rg "input|secret|skillenv|env_file|placeholder|ConfigRender"
```
