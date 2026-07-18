# Cloud Run deployment guide

```yaml
ai_card:
  id: command-center.cloud-run
  repository: Command Center
  title: Cloud Run Deployment Guide
  kind: operations_guide
  audience: [operator, engineer, ai_agent]
  status: implementation_ready
  owner_area: cloud deployment
  main_files: [Dockerfile, cloudbuild.yaml, services/memory/aria_memory/config.py]
  public_interfaces: ["PORT", "DATABASE_URL", "POST /mcp", "/.well-known/*"]
  provides: [Cloud Run and Cloud SQL deployment procedure, staging smoke gates]
  depends_on: [command-center.postgresql-proot, command-center.security-privacy]
  safe_edit_points: [Cloud Build substitutions, Secret Manager bindings, bounded scaling]
  risk_areas: [deploying without PostgreSQL, leaking secrets, unverified project identity]
  graph_rag_entities: [Cloud Run, Cloud SQL, Secret Manager, Cloud Build]
  last_verified: 2026-07-18
```

The deployment target is one combined static web, REST API, and stateless
Streamable HTTP MCP service on Cloud Run. Google Cloud is only the hosting
layer; Command Center does not expose GCP administration tools.

## Resources

- Artifact Registry repository for immutable images;
- Cloud Run service `codex-command-center`;
- Cloud SQL PostgreSQL instance for mutable hosted workspaces;
- Secret Manager versions for `OPENAI_API_KEY`, `DEMO_ACCESS_CODE`,
  `COOKIE_SECRET`, `DATABASE_URL`, and signing credentials;
- least-privilege runtime service account;
- Cloud Build service account with build, push, deploy, service-account-user,
  and secret-binding permissions;
- billing budget and log-based alerts.

SQLite remains the local development and test database. Do not treat `/tmp`
SQLite as durable production storage. The service refuses to start in
`APP_ENV=cloud` when `DATABASE_URL` is missing.

## Build

Submit from repository root so both Node and Python build stages see their
required files:

```sh
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_REPOSITORY=command-center,\
_CLOUD_SQL_INSTANCE="$PROJECT_ID:us-central1:command-center",\
_RUNTIME_SERVICE_ACCOUNT="command-center-runtime@$PROJECT_ID.iam.gserviceaccount.com"
```

The container reads Cloud Run’s `PORT`, binds `0.0.0.0`, serves the static export
and API from one origin, and keeps MCP requests independent of process-local
session state. Min instances may remain zero.

## Secrets and identity

Grant the runtime identity only:

- Secret Manager Secret Accessor on the named secrets;
- Cloud SQL Client on the one instance;
- permission to write Cloud Logging.

Do not grant project Editor, Owner, deployment, build, or general storage roles
to the runtime. Never bake `.env`, tokens, pairing codes, databases, or service
account keys into the image.

## Database contract

Production migrations must create the same domain constraints verified by local
SQLite tests:

- memory schema version stays 1;
- capability key is `(stable_id, version)`;
- handoff key is immutable ID plus unique `(lineage_id, version)`;
- handoff activation references a handoff;
- token hash is unique and revocation is timestamped;
- published handoff updates are rejected in the application transaction.
- architecture snapshots allow one active version per repository;
- document and section versions remain resolvable after a newer activation;
- architecture repository aliases remain workspace-scoped.

Run SQLite and PostgreSQL contract suites before promotion. Use a private IP or
Cloud SQL connector/Unix socket. Keep the database connection string in Secret
Manager. The production image installs the `postgres` dependency extra; local
Termux setup does not need to build the PostgreSQL driver.

The reproducible phone-local behavioral procedure is documented in
[PostgreSQL under Ubuntu PRoot](postgresql-proot.md). It verifies migrations,
snapshot transition, historical evidence, adapter restart, and active brief
retrieval, then removes its test schema.

## Smoke tests

Staging:

1. `GET /api/v1/status` without auth returns 401.
2. Browser demo auth succeeds and `Pair Codex` emits a one-time code.
3. Exchange the code and keep the returned token out of shell history.
4. Authenticated `POST /mcp` initialize returns
   `serverInfo.name=codex-command-center`.
5. `tools/list` returns ten tools.
6. Create, publish, and load a handoff for the declared repository.
7. Sync architecture revision one, publish a handoff, sync revision two, and
   verify the handoff still resolves revision-one evidence while a new task
   pack uses revision two.
8. Restart/revise the service and load the same handoff again.
9. Revoke the token and verify MCP returns 401.
10. Verify `/.well-known/*` returns the intentional structured 404.
11. Run a mobile screenshot/upload/paste and minimized-Aria pass.

Production repeats the authenticated MCP handshake, one read-only capability
search, and health check without creating demo memory.

## Logging and alerts

Use structured request fields for route, status, latency, workspace hash prefix,
MCP method, degraded state, and error code. Exclude headers and bodies. Create
alerts for:

- 5xx rate and latency;
- MCP initialize/call failures;
- Cloud SQL connection exhaustion;
- repeated auth failures;
- daily OpenAI quota/cost;
- monthly project budget threshold.

## Rollback

Cloud Run revisions are immutable. Save the last passing image digest and
database migration version. Route traffic back to the previous revision only
when its schema contract remains compatible. Handoff and capability versions
are append-oriented, so application rollback must not delete newer records.
