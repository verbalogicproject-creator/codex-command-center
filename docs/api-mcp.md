# REST API and MCP schemas

```yaml
ai_card:
  id: command-center.api-mcp
  repository: Command Center
  title: REST API and MCP Schemas
  kind: interface_reference
  audience: [engineer, integrator, ai_agent]
  status: implemented
  owner_area: API and MCP
  main_files: [services/memory/aria_memory/app.py, services/memory/aria_memory/mcp_app.py, services/memory/aria_memory/workspaces.py, services/memory/aria_memory/mcp.py, plugins/codex-command-center/scripts/mcp_server.py]
  public_interfaces: ["/api/v1", "POST /mcp", "command-center-task-pack-v2", "command-center-tour-script-v1", "command-center-visual-comparison-v1"]
  provides: [authenticated REST route inventory, MCP tool contract, transport parity reference]
  depends_on: [command-center.architecture-awareness, command-center.security-privacy, command-center.byok]
  safe_edit_points: [additive authenticated routes, shared MCP tool definitions]
  risk_areas: [stdio and HTTP schema drift, exposing write confirmation to models]
  graph_rag_entities: [FastAPI, MCP, CommandCenterClient]
  last_verified: 2026-07-19
```

FastAPI publishes the complete OpenAPI document at `/openapi.json` and an
interactive local reference at `/docs`. All workspace routes use an HttpOnly
browser cookie or `X-Command-Center-Token`.

## REST groups

| Group | Routes |
|---|---|
| Auth | `POST /api/v1/auth/demo`, `/auth/pair/start`, `/auth/pair`, `/auth/token/revoke` |
| Provider credentials | `POST/DELETE /api/v1/provider-credentials/openai`, `GET /provider-credentials/openai/status` |
| Capabilities | `GET/POST /api/v1/capabilities`, `GET /capabilities/{id}`, `POST /capabilities/recommend` |
| Screenshots | `POST /api/v1/screenshots/analyze`, `/screenshots/compare` |
| Projects and sessions | `GET /api/v1/projects`, `GET/POST /api/v1/sessions`, `PATCH /api/v1/sessions/{id}` |
| Handoffs | `GET/POST /api/v1/handoffs`, `GET/PATCH /handoffs/{id}`, `POST /handoffs/{id}/publish`, `/revoke`, `/versions`, `POST /handoffs/load` |
| Tours | `POST /api/v1/tours/script` |
| Architecture | `POST /api/v1/architecture/lint`, `/sync`, `/check`, `/brief`; `GET /architecture/health` |
| Context | `POST /api/v1/recall`, `/documents/recall`, `/context/pack` with target, explicit source repositories, and optional pinned evidence IDs |
| Evidence | `GET /documents/{id}`, `/memories/{table}/{id}`, `/graph`, `/timeline` |
| Aria | `POST /realtime/token`, `/chat/stream` |
| Memory | `GET/POST /proposals`, `POST /proposals/{id}/confirm`, `/reject`, `GET /audit` |
| Hooks | `POST /hooks/events` |

Validation failures use:

```json
{"error":{"code":"validation_error","message":"...","retryable":false}}
```

Provider credential responses never contain the credential or its prefix:

```json
{
  "provider": "openai",
  "configured": true,
  "expires_at": "2026-07-19T12:00:00Z",
  "persistence": "encrypted_browser_session"
}
```

The credential cookie is not an MCP authentication mechanism. Remote MCP
continues to use only the revocable Command Center workspace token.

## Remote MCP

The stateless Streamable HTTP endpoint is:

```text
POST https://<host>/mcp
X-Command-Center-Token: <revocable token>
Content-Type: application/json
```

Example initialize:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
  "protocolVersion":"2025-06-18",
  "capabilities":{},
  "clientInfo":{"name":"Codex","version":"1"}
}}
```

The endpoint accepts JSON-RPC batches and returns
`MCP-Protocol-Version: 2025-06-18`. It is sessionless and therefore safe across
Cloud Run cold starts. Notifications receive HTTP 202. Unsupported OAuth
well-known routes return a structured 404 directing users to browser pairing.

## MCP tools

| Tool | Required inputs | Behavior |
|---|---|---|
| `search_capabilities` | none | Search latest trusted capability versions |
| `recommend_capabilities` | `request`, `repository` | Ranked primary and alternatives with reasons |
| `get_capability` | `capability_id` | Exact or latest trusted instruction record |
| `load_handoff` | `handoff_id`, `repository` | Verified packet plus activation receipt |
| `build_task_pack` | `prompt` | `command-center-task-pack-v2`: task ArchitectureBrief plus durable context |
| `recall_context` | `query` | Same bounded v2 packet for recall wording |
| `get_evidence` | `source_id` | Versioned architecture document/section/edge/issue or durable evidence |
| `walk_dependencies` | `source_id` | Snapshot-preserving typed architecture paths |
| `get_timeline` | none | Recent durable evidence |
| `propose_memory_write` | `operation`, `payload`, `rationale` | Pending proposal only |

All tools except `propose_memory_write` declare `readOnlyHint=true`.
`propose_memory_write` is non-destructive and cannot confirm a write. There is
no code execution, native skill installation, tool installation, deployment,
or `confirm_memory_write` MCP operation.

The stdio adapter in `plugins/codex-command-center/scripts/mcp_server.py`
exposes the same names, schemas, annotations, and HTTP-backed results for clients
where remote headers are inconvenient.

## Architecture packet schemas

`command-center-architecture-brief-v1` includes repository identity, snapshot
receipt, compact health, selected cards and H2 sections, interfaces,
dependencies, safe edit points, risk areas, issues, versioned source receipts,
token accounting, omissions, degraded reasons, and a trace ID.

`command-center-task-pack-v2` wraps:

```json
{
  "packet_schema": "command-center-task-pack-v2",
  "architecture_brief": {"schema_version": "command-center-architecture-brief-v1"},
  "durable_context": {"facts": [], "episodes": [], "documents": []},
  "degraded": false
}
```

The architecture evidence prefixes are `adoc_`, `asec_`, `aedge_`, and
`aissue_`. Published handoffs retain these exact IDs even when their snapshot
becomes historical.

`command-center-tour-script-v1` contains a mode, model receipt, optional
handoff ID, 1–12 stable steps, generation time, and degradation reasons. Every
step includes a stable ID, target surface and region, bounded evidence IDs,
plain-text narration, action, and optional pause reason.
