# Computer Runtime Contract

Use this reference when a protocol change also needs to guide SDKs used by real client projects.

## Boundary Model

Separate Computer work into four layers:

| Layer | Owns | Does not own |
|---|---|---|
| Protocol | Cross-process, cross-language, cross-role interoperability visible to Agent, Server, Manager, Computer, marketplace, plugin, skill, tool, or MCP server participants. | Language-specific SDK API shape or internal implementation. |
| Computer Runtime Contract | The minimum stable SDK semantics a business client can rely on across SDKs. | Rust Builder shape, Python dataclass shape, trait names, class names, async runtime, locks, cache encoding, directory layout, or CLI UX. |
| SDK API Guidance | Recommended stable entry points and naming families for each SDK. | A single mandatory code shape across languages. |
| Client Responsibility | Multi-computer orchestration, persistence, UI state, account or Manager selection, user-facing connection policy, local secret storage, and audit flows. | Single Computer runtime internals, MCP server lifecycle, tool/resource calls, Socket.IO connection internals, and shutdown cleanup. |

## Decision Standard

Use this standard before writing requirements:

> If Rust SDK and Python SDK differences would make the same Manager, Agent, Computer, marketplace, plugin, skill, tool, or MCP server behave differently at runtime, the behavior belongs in protocol or conformance contract.
>
> If the difference only changes how a language caller writes code while final runtime behavior stays the same, it belongs to SDK implementation freedom or SDK API guidance.

## Protocol Scope

Put behavior in protocol when it defines the interoperability contract:

- Handshake, authentication, join office, disconnect, reconnect, and role/room visibility.
- External semantics after MCP server, tool, resource, SKILL, plugin, or marketplace capabilities are exposed.
- Wire schemas, field names, default values that cross the wire, error codes, status events, idempotency, and version compatibility.
- Externally visible lifecycle states, such as `created`, `booting`, `booted`, `connected`, `joined_office`, `stopping`, `stopped`, and `error`.
- Failure semantics visible outside the SDK, such as invalid config, MCP server startup failure, marketplace conflict, and plugin MCP server name conflict.
- Shared conformance tests that every compliant SDK must pass for observable behavior.

Do not put these in protocol:

- Whether Rust uses a Builder.
- Whether Python uses a dataclass.
- Whether SDK internals have a `ComputerRegistry`.
- Locking, runtime caching, watcher implementation, debounce interval, local directory layout, or lazy loading strategy.
- Whether marketplace manifests are cached locally when the cache is not externally observable.

## Computer Runtime Contract Scope

Use a Computer Runtime Contract when business clients need stable SDK behavior that is not itself a wire protocol.

The contract should define semantic capabilities such as:

- Create one runtime Computer from a declarative `ComputerConfig` plus `RuntimeOptions`.
- Start and stop the runtime.
- Connect and disconnect from Manager/Server.
- Synchronize config changes.
- List visible SKILLs/resources/tools as the SDK exposes them to the client.
- Install a plugin or add a marketplace when that is part of SDK responsibility.
- Shut down and release internal resources.

The contract should require semantic consistency across SDKs:

- The same config fixture parses to equivalent runtime intent.
- Defaults resolve equivalently.
- Lifecycle state transitions are equivalent.
- Error categories and retryability are equivalent.
- Marketplace and plugin MCP server mounting rules are equivalent.
- Shutdown releases resources and prevents stale events consistently.
- `sync_config` may be implemented as incremental update or rebuild, but must not expose inconsistent final state.

The contract should not require identical code shape:

- Rust may expose `Computer::from_config(config, runtime_options)`.
- Python may expose `Computer.from_config(config, runtime_options)`.
- Another SDK may expose a builder, factory, constructor, or async constructor.
- These are acceptable when the behavior, defaults, lifecycle, errors, and mounted capabilities match.

## SDK API Guidance

When writing SDK API guidance, describe stable semantic entry points rather than exact signatures:

| Capability | Stable semantic expectation |
|---|---|
| `from_config` or equivalent | Create a single runtime Computer from declarative config and runtime options. |
| `start` | Initialize local runtime resources and MCP server lifecycle needed before connection or service. |
| `stop` | Stop service activity without leaking externally visible running state. |
| `sync_config` | Apply a new config so the final externally visible runtime behavior matches the config. |
| `connect` | Establish the protocol connection and begin the configured office/session behavior. |
| `disconnect` | End the connection without destroying unrelated local config or persisted client state. |
| `list_skills` or equivalent | Return the SDK-visible SKILL view consistent with protocol-visible SKILL semantics. |
| `install_plugin` or equivalent | Install or mount plugin-provided capabilities according to contract rules. |
| `add_marketplace` or equivalent | Add marketplace sources and resolve conflicts according to contract rules. |
| `shutdown` | Release internal resources, stop MCP servers, disconnect, and prevent stale callbacks/events. |

Phrase requests as:

> SDKs need a cross-language Computer Runtime Contract that lets a business client create, start, sync, connect, disconnect, stop, and shut down one runtime Computer from declarative config, with consistent defaults, lifecycle states, error semantics, marketplace/plugin mounting behavior, and conformance tests.

Avoid requests like:

> Rust SDK must support this specific Builder shape.

## Client Boundary

Keep these responsibilities in a business client unless the SDK explicitly introduces a higher-level `ComputerManager` contract:

- Manage multiple Computer instances.
- Persist user or workspace config.
- Own UI state and user-facing connection strategy.
- Select account, Manager, Server, or office.
- Store secrets according to product policy.
- Track user operation audit logs.

Keep these responsibilities in the SDK single-Computer runtime:

- Manage one Computer runtime.
- Manage MCP server lifecycle.
- Handle tool/resource calls.
- Resolve and mount local SKILL, marketplace, and plugin capabilities.
- Own Socket.IO connection internals.
- Release internal resources during shutdown.

Specific boundary for config-to-runtime:

- Config schema can be protocol or protocol-adjacent contract.
- `from_config` behavior semantics belong in Computer Runtime Contract.
- `from_config` code shape belongs to each SDK.
- Multi-computer registry or orchestration belongs in the client unless a higher-level SDK manager is explicitly standardized.

## Conformance Tests

For runtime contract work, require shared conformance tests built from the same JSON fixtures and lifecycle scenarios.

Cover at least:

- Config parsing and default resolution.
- Lifecycle state transitions.
- Invalid config errors.
- MCP server startup failure errors.
- Marketplace conflict behavior.
- Plugin MCP server name conflict behavior.
- Plugin and marketplace mounting rules.
- `sync_config` final externally visible state.
- Shutdown cleanup and stale event prevention.

Conformance tests should validate public SDK results, public events, wire behavior, and error categories. They should not inspect private registries, caches, locks, task graphs, directory layouts, or language-specific class internals.
