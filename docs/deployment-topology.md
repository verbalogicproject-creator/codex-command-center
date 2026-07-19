# Three-service deployment topology

```yaml
ai_card:
  id: command-center.deployment-topology
  repository: Command Center
  title: Three-Service Deployment Topology
  kind: architecture_decision
  audience: [operator, engineer, ai_agent]
  status: implemented
  owner_area: cloud deployment
  main_files: [cloudbuild.three-service.yaml, deploy, apps/web, services/memory/aria_memory/mcp_app.py, services/memory/aria_memory/workspaces.py]
  public_interfaces: [frontend origin, REST API, Streamable HTTP MCP, Cloud SQL]
  provides: [frontend/backend/MCP service boundary, request routing, database ownership]
  depends_on: [command-center.cloud-run, command-center.security-privacy, command-center.api-mcp, command-center.byok]
  safe_edit_points: [service-specific images, frontend reverse proxy, MCP-only app entrypoint]
  risk_areas: [cross-origin cookie failure, duplicated tool handlers, SQLite on ephemeral storage]
  graph_rag_entities: [Command Center Web, Command Center API, Command Center MCP, Cloud SQL]
  last_verified: 2026-07-19
```

The production target is three independently deployable Cloud Run services
from one repository:

```text
Browser
  |
  v
command-center-web  (public static Next.js export + same-origin reverse proxy)
  |
  +-- /api/*, /docs, /openapi.json, /realtime/* --> command-center-api

Codex / MCP clients
  |
  v
command-center-mcp  (public endpoint, Command Center token required)
  |
  +-- shared provider-neutral handlers and workspace store
             |
             v
       Cloud SQL PostgreSQL
```

The service-specific applications, containers, build manifest, and cleanup
policy are implemented and locally verified. `implemented` describes the
source architecture; Cloud Run staging and Cloud SQL provisioning remain
deployment gates and are not claimed complete.

The current combined root Docker image remains the proven baseline until the
three service-specific images and staging smoke tests pass. Promotion must not
remove the rollback path to that combined revision.

## Frontend service

`command-center-web` contains only the static Next.js export and a minimal web
server. It owns no database, workspace token, OpenAI key, signing secret, or
durable state.

The web server proxies browser API paths to `command-center-api`. Keeping API
requests on the frontend origin preserves the existing HttpOnly, Secure,
SameSite=Lax workspace-cookie contract and avoids weakening cookies merely to
cross Cloud Run origins. The proxy must support:

- ordinary JSON requests;
- streaming Aria SSE without response buffering;
- screenshot request-size limits;
- WebRTC/Realtime token requests;
- forwarded host/protocol metadata;
- request timeouts longer than the largest bounded agent turn.

`NEXT_PUBLIC_API_BASE` stays empty in the production static build so browser
requests remain relative. The upstream API origin is a runtime server
configuration value, not a browser-visible secret.

## Backend service and databases

`command-center-api` owns browser authentication, pairing, capabilities,
screenshots, handoffs, architecture sync, context, Aria, memories, proposals,
audit, and REST documentation.

SQLite is a supported local-development and test adapter only. Mutable hosted
workspaces use Cloud SQL PostgreSQL. Cloud mode must continue refusing startup
without `DATABASE_URL`; no Cloud Run instance filesystem may be treated as
durable storage.

Migrations run once as an explicit release job before traffic promotion. They
must be backward compatible with the previous application revision so rollback
does not delete or reinterpret newer capability, handoff, architecture, token,
or activation records.

## Remote MCP service

`command-center-mcp` exposes only the stateless Streamable HTTP MCP boundary,
intentional `/.well-known/*` behavior, and a minimal unauthenticated liveness
route. It does not serve the browser application or general REST administration.

The MCP service imports the same canonical tool schemas and handlers as the API;
it must not fork business logic. It connects to the same workspace-scoped
PostgreSQL data and validates `X-Command-Center-Token` by its server-side hash.
Every tool call is independent and scale-to-zero safe.

The local stdio plugin remains a transport adapter. It answers
`initialize`/`tools/list` locally and forwards `tools/call` to this hosted MCP
service. Direct remote clients use the same schemas and results.

## Identity and secrets

Use separate least-privilege runtime service accounts:

- web: invoke the API if IAM-level private ingress is later introduced; no
  Secret Manager or Cloud SQL access by default;
- API: Cloud SQL Client plus access only to cookie, signing, and BYOK-envelope
  encryption secrets;
- MCP: Cloud SQL Client plus access only to MCP signing secrets required by
  canonical handlers.

The initial browser-facing API may allow unauthenticated Cloud Run invocation
because application routes enforce Command Center authentication. This does not
make protected API data public. A later same-origin identity-aware proxy may
make the API service IAM-private without changing browser contracts.

Never expose `DATABASE_URL`, workspace tokens, cookie or envelope secrets,
pairing codes, service-account keys, or user OpenAI credentials to the frontend
image, repository, build arguments, URLs, or logs. The production Secret
Manager inventory contains no operator `OPENAI_API_KEY`; users provide
short-lived encrypted session credentials under the
[BYOK contract](byok.md). The default `command-center` demo code is local only
and must not be a production security boundary.

## Build and promotion

Cloud Build should produce three immutable image digests from one commit:

1. `command-center-web`;
2. `command-center-api`;
3. `command-center-mcp`.

Deploy to staging first. Record the source revision, image digests, migration
version, frontend origin, API origin, MCP URL, and Cloud SQL instance.
Production promotion reuses the exact passing digests rather than rebuilding.
`cloudbuild.three-service.yaml` implements the parallel build-and-push boundary;
it intentionally performs no deployment or migration. Service promotion is a
separate reviewed operation after PostgreSQL, IAM, secrets, BYOK, and staging
configuration exist.

The initial shared region is `me-west1` (Tel Aviv), which supports Cloud Run,
Cloud SQL for PostgreSQL, and Artifact Registry. Keep images, services, and the
database in that region. Initial staging uses generated `run.app` URLs; a custom
domain in this region requires a later load-balancing or supported hosting
layer.

## Staging gates

1. Frontend root and static assets return HTTP 200.
2. Same-origin browser login sets and reuses a Secure HttpOnly cookie.
3. Unauthenticated protected API and MCP requests return 401.
4. Authenticated MCP `initialize`, `tools/list`, and all read-only calls work
   after scale-to-zero cold start.
5. Capability recommendation selects the exact Taste-guided redesign workflow.
6. A screenshot remains non-retained and every visual finding is labelled as an
   inference.
7. A published handoff pins capability, architecture, and evidence versions;
   Codex loads it and begins the interview without editing.
8. API and MCP produce identical tool schemas and task-pack receipts.
9. Restarting all three services preserves handoffs, tokens, snapshots, and
   evidence through PostgreSQL.
10. Token revocation, repository mismatch, stale architecture, optional dense
    failure, and rollback behavior remain visible and safe.
11. Mobile browser, reduced-motion, keyboard, screenshot paste/upload, voice,
    and minimized-Aria checks pass through the deployed frontend.
12. BYOK redaction, expiry, deletion, workspace isolation, and no-key offline
    behavior pass without an operator OpenAI credential.

Only after these gates pass should traffic move to production.
