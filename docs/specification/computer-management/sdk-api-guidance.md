# SDK API Guidance

This document is non-normative. It describes recommended SDK API capabilities for implementing the [Computer Runtime Contract](runtime-contract.md) without prescribing language-specific class, trait, builder, constructor or async runtime shapes.

## 1. Stable Capability Families

SDKs are encouraged to expose public entry points for these capability families:

| Capability family | Stable semantic expectation |
|---|---|
| create from config | Create one runtime Computer from declarative config and runtime options |
| start / stop | Initialize and stop local runtime service activity |
| connect / disconnect | Establish and end SMCP connection without destroying durable config |
| join / leave office | Join or leave an Office when not folded into connect/disconnect |
| sync config | Apply a new config so final public runtime behavior matches it |
| query projection | Return SDK-visible tools, config, resources, Desktop and SKILL views consistent with protocol projection |
| plugin lifecycle | Install, enable, disable and uninstall plugin-contributed capabilities |
| marketplace lifecycle | Add, sync/refresh, list and prune marketplace sources |
| input values | Resolve, set, clear and inspect input values without exposing secrets to Agent |
| diagnostics | Return lifecycle state, degraded components, validation errors and last failures |
| shutdown | Release resources and prevent stale callbacks/events |

The exact names are SDK-specific. For example, one SDK may expose a builder, another may expose a factory, and another may use an async constructor. Conformance is based on behavior.

## 2. Recommended API Shape Principles

SDKs are encouraged to:

1. Separate config parsing from side effects. Creating a runtime from config should not connect to Server or execute tools.
2. Make lifecycle operations explicit and idempotent where practical.
3. Return public lifecycle state and diagnostics instead of requiring callers to inspect logs or private fields.
4. Distinguish `disconnect`, `stop` and `shutdown`.
5. Provide a single `sync_config` semantic operation even if the implementation internally rebuilds the runtime.
6. Provide typed or structured error categories aligned with [Runtime Contract §6](runtime-contract.md#6-error-categories).
7. Keep management diagnostics separate from Agent-facing protocol payloads.
8. Allow callers to inject business auth fields without placing secrets into `a2c_version`, `role`, update notifications or Agent-visible config.

## 3. Config And Defaults

SDKs may use language-native types, but should support shared JSON fixtures for conformance.

Recommended default behavior:

| Area | Guidance |
|---|---|
| namespace | Default to `/smcp` |
| protocol version | Use the SDK's declared A2C-SMCP protocol version in URL query |
| auth role | Always include `auth.role = "computer"` for Computer connections |
| auto connect | Document whether start automatically connects; prefer explicit connect for embedders |
| auto reconnect | If supported, make behavior configurable and observable |
| disabled servers | Preserve config but exclude capability from Agent-facing projection |
| forbidden tools | Exclude from tools and reject successful execution |
| marketplace reconcile | Prefer additive-only startup reconcile and explicit prune/gc |
| plugin conflict | Reject foreign MCP Server name conflicts before mounting |
| secret values | Resolve locally and never include in Agent-facing projection |

## 4. Lifecycle API Guidance

### 4.1 Create

SDKs may provide any equivalent of:

```
runtime = create_computer(config, runtime_options)
```

This operation should validate shape and resolve defaults, but avoid network and MCP process side effects.

### 4.2 Start

`start` should initialize local resources, registries, blob resolvers, watchers and MCP manager intent. If start eagerly launches MCP Servers, SDKs should document the policy and expose startup failures as public diagnostics.

### 4.3 Connect

`connect` should take a Server URL and optional connection options. SDKs should make the final handshake inspectable enough for tests to verify:

- `a2c_version` is in URL query.
- `auth.role` is `"computer"`.
- caller-supplied auth payload is included without leaking MCP credentials.
- `server:join_office` is sent when configured.

### 4.4 Sync Config

SDKs should expose one operation that applies a new desired config. It can be implemented as:

- incremental update;
- diff-and-apply;
- full rebuild behind stable identity;
- stop/start with projection preservation.

SDKs should document whether in-flight tool calls continue, are cancelled, or are allowed to finish during sync. Regardless of implementation, the final projection must match the new config.

### 4.5 Shutdown

SDKs should provide a terminal cleanup operation. After it completes:

- no update notification should be emitted;
- no watcher should call stale callbacks;
- no old Socket.IO client should ack new requests;
- owned MCP server resources should be stopped or detached according to documented policy.

## 5. Plugin And Marketplace API Guidance

SDKs are encouraged to expose plugin and marketplace operations as management APIs, not Agent-facing protocol events.

Recommended plugin operations:

| Operation | Guidance |
|---|---|
| install | Materialize plugin, validate manifest, precheck MCP name conflicts, register SKILL/MCP/input contributions |
| enable | Mark plugin enabled and reconcile contributions |
| disable | Mark plugin disabled and make contributions invisible/non-callable |
| uninstall | Remove plugin records and teardown owned contributions unless caller chooses keep-server policy |
| info/list | Return management diagnostics and provenance only to trusted caller |

Recommended marketplace operations:

| Operation | Guidance |
|---|---|
| add | Add a source declaration after trust/policy approval |
| sync/refresh | Fetch/update declared sources and register enabled plugin SKILLs |
| list | Return source status and diagnostics to trusted caller |
| prune | Explicitly remove orphan materialization after caller confirmation |

SDKs may support ledger-only operations for non-live contexts, but should document that Agent-facing projection changes require a live runtime reconcile.

## 6. Inputs And Secret Guidance

SDKs are encouraged to:

1. Keep input definitions separate from resolved values.
2. Support plugin-scoped input disambiguation to avoid same bare id collision.
3. Avoid logging resolved secret values.
4. Expose public diagnostics for missing input values without including actual secrets.
5. Treat `.skillenv` and local secret files as local-only; never include their contents in `client:get_skill`, `client:get_blob`, `client:get_config` or tool metadata.

## 7. Testing Guidance

SDKs should maintain both protocol conformance tests and runtime contract tests:

| Test class | Validates |
|---|---|
| wire conformance | `client:*` response shape, flat `ErrorPayload`, update notifications, room behavior |
| runtime conformance | lifecycle state transitions, `sync_config`, plugin/marketplace semantics, shutdown cleanup |
| projection conformance | final `get_config`/`get_tools`/`get_skills`/`get_desktop` views after management operations |
| security conformance | no secret/path leakage, sandbox boundaries, blob handle opacity |
| cross-SDK fixture conformance | Python/Rust/TypeScript parse the same JSON fixture to equivalent runtime intent |

See [Conformance Tests](conformance-tests.md) for the shared checklist.

## 8. Migration Guidance

SDKs adding this runtime contract to existing APIs are encouraged to:

1. Keep existing constructors/builders working as compatibility wrappers.
2. Add shared fixture parsing before changing CLI UX.
3. Introduce lifecycle state diagnostics without changing Agent-facing wire behavior.
4. Add conformance tests for current behavior before refactoring internals.
5. Keep marketplace/plugin management APIs explicitly trusted-local.

## 9. Non-Goals

This guidance does not standardize:

- a required `Computer` class name;
- exact builder/factory signatures;
- local home layout;
- settings file names;
- watcher implementation;
- process supervision model;
- retry scheduler;
- CLI commands;
- UI flows.
