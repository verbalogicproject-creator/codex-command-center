# Troubleshooting

```yaml
ai_card:
  id: command-center.troubleshooting
  repository: Command Center
  title: Troubleshooting Manual
  kind: operations_guide
  audience: [user, engineer, operator, ai_agent]
  status: implemented
  owner_area: operations
  main_files: [plugins/codex-command-center/scripts/health.py, plugins/codex-command-center/scripts/architecture.py]
  public_interfaces: [health check, architecture lint status and sync]
  provides: [diagnosis for auth architecture MCP voice PostgreSQL and deployment]
  depends_on: [command-center.codex-plugin, command-center.postgresql-proot]
  safe_edit_points: [read-only health checks, explicit sync after lint]
  risk_areas: [weakening guards to hide errors, deleting active persistence]
  graph_rag_entities: [HealthCheck, ArchitectureHealth]
  last_verified: 2026-07-18
```

## Service and browser

**The browser says sign-in required.** Confirm the API and web app use the same
hostname (`localhost` versus `127.0.0.1` changes cookie scope), then sign in
again.

**Screenshot analysis is degraded.** The builder still validates and hashes the
image and creates local inference labels. Configure `OPENAI_API_KEY` to enable
Sol multimodal analysis. Confirm the configured deep model supports image input.

**Upload returns 422.** Use PNG, JPEG, or WebP under 10 MB and at least 32×32
pixels. Renaming a file extension does not change its detected MIME type.

**The builder omits sources.** This is expected under the token bound. Inspect
`omitted_candidates`, `degraded`, and the evidence receipts.

## Architecture awareness

**`architecture.py` cannot find a manifest.** Run it anywhere inside a checkout
that contains `.command-center/architecture.yaml`. The helper walks upward but
will not cross into another repository.

**Lint reports a missing card.** Add a complete root-frontmatter declaration or
fenced YAML `ai_card`. Use `architecture.py scaffold` only for a new file; it
refuses to overwrite existing content.

**Sync reports a repository conflict.** The manifest repository name and every
card’s `repository` must normalize to the same value. Fix the declaration; do
not weaken the guard.

**SessionStart says `local_snapshot_drift`.** The hook sent hashes only. Review
the changed docs, lint, and run explicit sync when the new corpus is ready.

**The brief says `dense_architecture_retrieval_unavailable`.** Declared and
lexical section ranking still works. The degraded marker prevents a false claim
that dense section embeddings were used.

**An unknown checkout gets no context.** This is intentional repository
isolation. Add its canonical ID or checkout name as a manifest alias and sync
that repository; unfiltered fallback is not supported.

## Pairing and MCP

**Pairing code expired.** Generate a new code; each code lasts five minutes and
works once.

**Health check is unauthorized.** Pair again or check
`COMMAND_CENTER_STATE_DIR`. The token file must be writable and readable only by
the current user.

**Remote MCP returns 401.** Send `X-Command-Center-Token`, not a URL parameter or
cookie copied from browser storage. Check token revocation.

**`load_handoff` says repository mismatch.** Open Codex in the repository named
by the handoff. Do not bypass this check; create a new repository-scoped
handoff if needed.

**Published handoff cannot be edited.** This is intentional. Use
`POST /api/v1/handoffs/{id}/versions` to create a new draft.

**Stdio server starts but tool calls fail.** `tools/list` is local, while calls
reach `COMMAND_CENTER_URL`. Run `scripts/health.py` and check network access.

**Old plugin still appears.** Remove `command-center-memory`, install
`codex-command-center` v0.3 through the cache-busted local update flow, pair
again, and start a new Codex thread. See
`plugins/codex-command-center/MIGRATION.md`.

## Hooks

**No session briefing appears.** Inspect `/hooks`, trust the project/plugin hook
definitions, and verify `SessionStart` can reach the service.

**Stop creates too many proposals.** Leave
`COMMAND_CENTER_STOP_PROPOSALS` unset. Stop proposals are opt-in because the hook
runs after every Codex turn.

**Telemetry contains less than expected.** The sanitizer intentionally drops
raw prompts, tool output, secrets, and undeclared keys.

## Cloud Run

**Container fails readiness.** Confirm `PORT` is passed to Uvicorn, the build
context is repository root, and the static web export exists.

**Cold-start MCP fails.** Retry initialize once, verify request timeout, and
confirm no process-local session state is required. Pair-code hashes, workspace
tokens, and handoffs must all use durable hosted storage.

**Well-known OAuth probes return 404.** That is the intended behavior for the
current browser-code pairing flow.

**PostgreSQL migration fails on DDL.** Run the real behavioral test, not only
the static SQL contract. The row factory must accept command-only results whose
cursor description is `None`. See [PostgreSQL under proot](postgresql-proot.md).

**Docker is unavailable on Android.** Run the root Docker build on a
Docker-capable laptop or through Cloud Build after the local SQLite,
PostgreSQL, web, plugin, and security gates pass.

## Verification commands

```sh
pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
scripts/security-scan.sh
python ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/codex-command-center
```
