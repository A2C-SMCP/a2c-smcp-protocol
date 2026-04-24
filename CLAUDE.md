# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **A2C-SMCP Protocol Specification** repository - a documentation-only repo defining how Agents and Computers communicate through a Socket.IO-based remote tool invocation protocol. The deliverable is the specification documents themselves, built using MkDocs and deployed to both GitHub Pages and doc.turingfocus.cn.

**Current Version**: 0.2.0

## Repository Structure

```
a2c-smcp-protocol/
├── .github/
│   └── workflows/
│       └── deploy-pages.yml  # GitHub Pages 自动部署
├── docs/                      # 文档源文件 (MkDocs docs_dir)
│   ├── index.md              # 首页
│   ├── specification/        # 协议规范
│   │   ├── index.md          # 概述
│   │   ├── architecture.md   # 架构设计
│   │   ├── events.md         # 事件定义
│   │   ├── data-structures.md# 数据结构
│   │   ├── room-model.md     # 房间模型
│   │   ├── error-handling.md # 错误处理
│   │   └── security.md       # 安全考虑
│   └── appendix/
│       └── faq.md            # 常见问题
├── scripts/                   # 部署脚本
│   └── docs/
│       ├── config.py         # 配置管理
│       ├── tasks.py          # Invoke 任务
│       └── version_utils.py  # 版本工具
├── mkdocs.yml                # MkDocs 配置
├── pyproject.toml            # 项目配置 (版本号单一来源)
├── tasks.py                  # Invoke 入口
└── README.md                 # 开发指南
```

## Core Design Philosophy

### Agent-User Capability Equivalence

**A2C-SMCP treats Agent and User as capability-equivalent entities.** The "Agent" vs "User" distinction is an **identity label**, not a **capability boundary** — neither role has privileged operations the other cannot perform.

**At the protocol level, there is no "User" role.** When User actions (triggered via UI co-deployed with Server) need to reach Computer, they go through the **Business Layer User Proxy Pattern**:

```
UI → HTTP(Server business layer) → emit client:* with real Agent identity → Computer
```

From A2C protocol's perspective, every `client:*` event is **always Agent-originated**. The User-to-Agent translation (Agent name lookup, audit logging, response gating) lives entirely in the **business layer**, invisible to the protocol. This keeps the three-role model pure and decouples protocol evolution from User features.

**Invariants of the proxy pattern** (do not violate):
- `AgentCallData.agent` MUST contain the room's **real** Agent name (business layer maintains it; no sentinel names)
- Room MUST have an Agent; no Agent → user operation rejected at business layer
- Agent is **not informed** of User's intermediate operations; results reach Agent only via a separate business action when User explicitly sends chosen content
- Protocol-level audit records Agent-origin; User session/audit is a business-layer concern
- Spec prose MUST NOT relax `client:*` source semantics ("MAY be originated by Server" etc.) — the protocol definition stays "Agent → Server → Computer"

Full pattern details and evolution notes live in memory: `business_layer_user_proxy_pattern.md`.

**Tension with MCP**: MCP protocol defines `audience=["user"]` vs `audience=["assistant"]` as meaningful routing distinctions. A2C-SMCP treats `audience` as a **hint** (UX/rendering preference), **not** a capability gate. When protocol behavior diverges from MCP's audience semantics, **spec must explicitly note** the divergence is intentional — this prevents future contributors from "fixing" it back to MCP's stricter interpretation.

**Do not erode this principle by accident**: adding role-gated capabilities (e.g., "only Agent MAY call X"), `origin` fields, `user:*` prefixes, or a "User" role requires an explicit, non-role-semantic justification (isolation, credential boundary, etc.) — bring such proposals up before coding them.

## Architecture Essentials

### Three-Role Model
- **Agent** (1 per room max): Tool call initiator, typically an AI system
- **Server** (1 logical): Signal hub for routing, room management, broadcasts
- **Computer** (multiple per room): Hosts MCP services, executes tools

### Event Routing Convention
| Prefix | Flow | Handler |
|--------|------|---------|
| `client:*` | Agent → Server → Computer | Computer processes, Server routes |
| `server:*` | Client → Server | Server handles room/config management |
| `notify:*` | Server → Broadcast | Room-scoped notifications |

Protocol convention: `client:*` is always Agent-originated at protocol level. If a User action needs to reach Computer, it goes through the Business Layer User Proxy Pattern described above — the translation is business-layer concern and is invisible to Computer. Do not describe User as a protocol source in spec prose.

### Room Isolation Rules
- One Agent maximum per room (exclusive)
- Multiple Computers can join the same room
- Cross-room access is forbidden at the Server layer
- All events scoped to room boundaries

## Key Protocol Patterns

### Tool Call Flow
```
Agent ─[client:tool_call]──→ Server ─[routes via name_to_sid]──→ Computer
      ◄────────[CallToolResult]──────────────────────────────────┘
```

### Message Correlation
- All requests include `req_id` for deduplication and correlation
- Responses echo back the `req_id`
- Timeouts specified in seconds (integer)

### Security Model
- **Zero credential propagation**: Secrets stay on Computer, never reach Agent
- **Room-based isolation**: Enforced at Server layer
- **Transport**: TLS 1.2+ required for public deployments

## Working with This Repository

### Document Editing
When modifying specification documents:
- TypedDict definitions in `docs/specification/data-structures.md` are the source of truth for message schemas
- Event definitions in `docs/specification/events.md` must match data structure definitions
- Error codes in `docs/specification/error-handling.md` should cover new failure modes
- Security implications should be documented in `docs/specification/security.md`

### Documentation Build & Deploy

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install dependencies
uv venv && source .venv/bin/activate
uv pip install -e ".[docs]"

# Local preview (hot reload)
inv docs.serve

# Build versioned docs
inv docs.build

# Deploy to GitHub Pages
inv docs.deploy-github

# Deploy to company server
inv docs.deploy

# Deploy to both platforms
inv docs.deploy-all
```

### Version Management
- Version number is defined in `pyproject.toml` (single source of truth)
- Use `bump-my-version` for version updates
- Multi-version docs managed by `mike`

## SDK Implementations

SDK implementations are in separate repositories:
- Python SDK: `github.com/A2C-SMCP/python-sdk`
- Rust SDK: `github.com/A2C-SMCP/rust-sdk`
