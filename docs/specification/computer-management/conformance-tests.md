# Computer Management Conformance Tests

本文定义 Computer Management Plane 的 SDK conformance checklist。测试应验证公开 SDK 结果、公开事件、wire 行为、错误分类和安全边界；不得检查私有 registry、缓存、锁、任务图、目录布局或语言专属类型。

## 1. Test Levels

| Level | Subject | Required observation |
|---|---|---|
| Protocol projection | Running Computer through SMCP Server and Agent | `client:*` responses, `server:update_*`, `notify:*`, flat `ErrorPayload` |
| Runtime contract | Public SDK runtime object | lifecycle state, public diagnostics, public errors, final projection |
| Fixture parity | Shared JSON config fixtures | equivalent runtime intent across SDKs |
| Security | Public SDK and Agent-facing protocol | no secret/path leakage, sandbox and blob boundaries |

## 2. Shared Fixtures

Conformance suites SHOULD use the same JSON fixtures across SDKs. The exact on-disk location is SDK-specific, but each SDK SHOULD be able to load fixtures equivalent to:

### 2.1 Minimal Runtime

```json
{
  "name": "computer-a",
  "mcp_servers": [],
  "inputs": [],
  "plugins": {},
  "marketplaces": {}
}
```

Expected:

- create succeeds;
- start reaches `started` or equivalent;
- `client:get_config` returns empty `servers`;
- `client:get_tools` returns empty `tools`;
- shutdown releases resources.

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

Expected:

- enabled server appears in `client:get_config`;
- tools exposed by the fixture server appear in `client:get_tools`;
- `client:tool_call` returns MCP `CallToolResult`;
- removing or disabling the server removes tools from subsequent projection.

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

Expected:

- forbidden tool does not appear in `client:get_tools`;
- forbidden tool cannot be successfully executed;
- `safe_read` metadata appears under `meta["a2c_tool_meta"]` as a JSON string.

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
  "plugins": {
    "audit@acme": true
  }
}
```

Expected:

- startup reconcile is additive;
- enabled plugin SKILLs appear in `client:get_skills`;
- plugin-contributed MCP servers appear through normal config/tool projection;
- disabling `audit@acme` removes or hides its contributed capabilities;
- removing declaration alone does not delete materialized marketplace until explicit prune/gc.

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

Expected:

- resolved token is used only locally;
- `client:get_config` does not expose the resolved token;
- errors and diagnostics visible to Agent do not contain the token;
- plugin-scoped input fixtures with same bare id do not cross-contaminate values.

## 3. Runtime Contract Checklist

### 3.1 Create From Config

- Given a valid minimal fixture, creating a runtime succeeds without network access.
- Given invalid JSON shape, SDK returns a public `validation` error.
- Given invalid plugin id shape, SDK returns a public `validation` error.
- Creating a runtime does not start MCP tool execution.
- Creating a runtime does not emit `server:update_*`.

### 3.2 Start

- `start` initializes local projection for valid config.
- Startup with one failing MCP Server enters `degraded` or returns partial diagnostics without exposing that server's tools as usable.
- Startup never exposes secret values in public diagnostics.
- Repeated `start` is idempotent or returns a clear lifecycle conflict.

### 3.3 Connect And Join

- `connect` sends `a2c_version` in URL query.
- `connect` sends `auth.role = "computer"`.
- Caller-provided business auth fields are included when configured.
- MCP credentials and `.skillenv` contents are not included in auth payload.
- Join Office uses `server:join_office` with `role = "computer"` and the configured Computer name.
- Protocol version mismatch is categorized as `protocol_version`.
- Auth failure is categorized as `auth`.

### 3.4 Sync Config

- Adding an MCP Server through `sync_config` makes its tools visible after success.
- Disabling an MCP Server through `sync_config` removes its tools from `client:get_tools`.
- Removing an MCP Server through `sync_config` makes `client:get_resources` for that server return `4014`.
- Changing tool metadata updates `SMCPTool.meta`.
- Changing SKILL sources updates `client:get_skills`.
- If joined to an Office, each projection-changing sync emits the relevant `server:update_*` request or an equivalent coalesced set.
- Partial failure never leaves ambiguous duplicate `tool_name` routing visible.

### 3.5 Disconnect, Stop, Shutdown

- `disconnect` ends Socket.IO connection without deleting durable desired state.
- After `disconnect`, local management changes do not emit update events to the previous Office.
- `stop` prevents new Agent-facing service activity after completion.
- `shutdown` disconnects if needed, stops owned MCP activity and stops watchers/timers.
- After `shutdown`, stale callbacks do not emit `server:update_*`.
- Repeated `shutdown` is idempotent or returns a clear lifecycle state result.

## 4. Protocol Projection Checklist

### 4.1 Config

- `client:get_config` returns current safe `servers` and `inputs`.
- Disabled servers are either absent or clearly not active according to existing config semantics; they do not expose callable tools.
- Secret values, OAuth tokens, API keys, `.skillenv` contents and local credential file contents are absent.
- Unknown management diagnostics are absent.

### 4.2 Tools

- `client:get_tools` returns only enabled, non-forbidden, uniquely routable tools.
- `a2c_tool_meta` is a JSON string when complex A2C metadata is present.
- Duplicate tool names are resolved by alias, disable/reject, or other deterministic policy before exposure.
- `client:tool_call` for removed/disabled/forbidden tools cannot succeed.

### 4.3 Resources

- Known MCP Server with `resources` capability returns transparent `resources/list` page.
- Unknown `mcp_server` returns flat `ErrorPayload` with `code = 4014`.
- Server lacking `resources` capability returns flat `ErrorPayload` with `code = 4015`.
- Response is not filtered by scheme, `_meta`, annotations or content.

### 4.4 SKILL

- `client:get_skills` returns active refs and excludes orphan/removed/disabled plugin refs.
- Required fields `name`, `source`, `path`, `description` are present.
- Invalid `name` in `client:get_skill` returns `4016`.
- Missing/orphan/removed name returns `4014`.
- Traversal, absolute path, `.skillenv`, forbidden file and not-found `rel_path` return `4017`.
- Text under inline budget returns `body`; binary or large text returns `blob_handle`; never both.

### 4.5 Blob

- `client:get_blob` treats handle as opaque and returns chunks by absolute offset.
- Invalid handle returns `4018` with `details.reason = "invalid_handle"` or equivalent.
- Source removed after handle mint returns `4018` with `gone` or equivalent.
- Out-of-range offset returns `4018` with `range` or equivalent.
- `total_size` and `sha256` remain stable within a logical read.
- Blob access cannot read arbitrary local files.

### 4.6 Desktop

- `client:get_desktop` returns only valid `window://` rendered entries.
- Exact `window` filter returns only matching URI or empty list.
- Invalid/empty/unrenderable windows are skipped.
- Management diagnostics and local paths are not rendered into Desktop content.

### 4.7 Cancellation And Timeout

- `server:tool_call_cancel` remains fire-and-forget; no ack is required.
- Unknown or completed `req_id` is ignored by Computer without new protocol error.
- Successful cancellation returns original `client:tool_call` ack as `CallToolResult(isError=true)` with result-level `meta.a2c_cancelled = true`.
- Timeout returns `CallToolResult(isError=true)` and SHOULD include result-level `meta.a2c_timeout = true`.

## 5. Marketplace And Plugin Checklist

- Marketplace reconcile installs missing declared marketplace sources.
- Source change causes the old source projection to be replaced after reconcile.
- `autoUpdate` or explicit refresh updates the declared source.
- Undeclared materialized marketplaces are not deleted during additive startup reconcile.
- Explicit prune removes marketplace materialization and unregisters its active SKILLs.
- Plugin install validates `<plugin>@<marketplace>` shape.
- Plugin install fails if marketplace is unknown.
- Plugin install rejects foreign MCP Server name conflict.
- Reinstall/enable of plugin-owned MCP Server is idempotent.
- Plugin disable makes contributed SKILLs/tools/MCP resources invisible or non-callable.
- Plugin uninstall removes its records and tears down owned bundled MCP servers unless keep-server policy is explicitly chosen.
- Plugin-scoped inputs are injected before plugin server config rendering.

## 6. Security Checklist

- Agent cannot invoke management mutation through any `client:*` event.
- Management errors containing local paths are not copied into Agent-facing `ErrorPayload.details`.
- Secret values do not appear in `client:get_config`, `client:get_tools`, `client:get_desktop`, `client:get_skill`, `client:get_blob`, update notifications or tool metadata.
- SKILL sandbox prevents traversal, symlink escape and forbidden file access.
- Blob handle parsing re-runs source authorization/boundary checks.
- Cleanup operations refuse to delete outside the authorized Computer local boundary.
- Policy-rejected marketplace/plugin/source contributes no visible capability.

## 7. Cross-SDK Parity Matrix

Each SDK SHOULD report pass/fail for:

| Area | Python | Rust | TypeScript | Notes |
|---|---|---|---|---|
| Config fixture parsing | required | required | recommended | Same fixture, equivalent runtime intent |
| Lifecycle transitions | required | required | recommended | Public state or mapped diagnostics |
| Wire projection | required | required | recommended | Through test Server + Agent |
| Marketplace/plugin | required if feature exists | required if feature exists | recommended | Feature-gated allowed |
| Secret safety | required | required | required | No feature gate |
| Shutdown cleanup | required | required | recommended | Public effects only |

Feature-gated SDKs may mark marketplace/plugin tests as not applicable only if the SDK does not claim those management capabilities. Protocol projection and secret safety tests remain required for any Computer SDK.

## 8. Evidence Coverage

The current Python and Rust SDKs already contain evidence for most checklist areas:

| Area | Python tests/source | Rust tests/source |
|---|---|---|
| Computer lifecycle and tools | `tests/unit_tests/computer/*`, `tests/integration_tests/computer/*`, `a2c_smcp/computer/computer.py` | `crates/smcp-computer/tests/*`, `tests/v022_integration_matrix.rs`, `crates/smcp-computer/src/computer.rs` |
| Socket.IO Computer client | `a2c_smcp/computer/socketio/client.py` | `crates/smcp-computer/src/socketio_client.rs` |
| Settings and reconcile | `a2c_smcp/computer/settings/*`, `tests/unit_tests/computer/settings/*` | `crates/smcp-computer/src/settings/*` unit tests |
| SKILL/blob/Desktop | `tests/e2e/test_v02_skill_blob_e2e.py`, `tests/integration_tests/test_blob_transfer.py`, desktop tests | `tests/v022_integration_matrix.rs`, `crates/smcp-computer/tests/desktop_integration.rs`, blob/skill modules |

These are evidence pointers, not mandatory file paths for future SDKs.

## 9. Compatibility

Compatibility label: **Runtime-contract + SDK conformance**.

The tests do not require wire schema changes. They may reveal SDK behavior gaps that should be fixed as SDK conformance work.
