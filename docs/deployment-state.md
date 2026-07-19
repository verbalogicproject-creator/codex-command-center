# Deployment state and continuation receipt

```yaml
ai_card:
  id: command-center.deployment-state
  repository: Command Center
  title: Deployment State and Continuation Receipt
  kind: operations_receipt
  audience: [operator, engineer, ai_agent]
  status: active
  owner_area: cloud deployment
  main_files: [cloudbuild.three-service.yaml, deploy, docs/cloud-run.md, docs/deployment-topology.md]
  public_interfaces: [Google Cloud project, Artifact Registry, staging continuation gate]
  provides: [idempotent deployment continuation, current external resource state]
  depends_on: [command-center.deployment-topology, command-center.cloud-run]
  safe_edit_points: [append verified resource receipts after successful commands]
  risk_areas: [duplicating resources, deploying unreconciled source, unbounded Cloud SQL spend]
  graph_rag_entities: [Google Cloud, Artifact Registry, Cloud Run, Cloud SQL]
  last_verified: 2026-07-19
```

This card records live external state verified from the Termux deployment
environment. The public v0.5 staging workspace is deployed; the manual
voice/browser, clean-Linux Codex, dogfood design, and v1.0 promotion gates
remain open.

## Verified Google Cloud target

| Field | Value |
|---|---|
| Project ID | `codex-command-centet` |
| Project number | `67134152472` |
| Shared region | `me-west1` |
| Billing | enabled |
| Release image commit | `a4f67df8b9b88f353dbb14486033b357f53284c5` |
| Release branch | `termux/taste-byok-deployment` |
| Cloud Build | `3466c6a0-d53d-4984-814c-8f3fbef65eb9` |
| Monthly budget | ₪153, approximately USD 50 at the 2026-07-17 representative rate |

The project ID intentionally ends in `centet`; do not “correct” it in commands.
Cloud Run, Cloud SQL for PostgreSQL, and Artifact Registry are available in the
selected Tel Aviv region.

## Existing resources

Artifact Registry contains one standard Docker repository:

```text
projects/codex-command-centet/locations/me-west1/repositories/command-center
```

The repository contains the three release packages tagged with the exact
release commit. The deployed digests are:

| Service | Digest |
|---|---|
| web | `sha256:cae5efe71ca102a6ec21f74b7d88e0c90bcf0e9f983ef030f2099d7980e4f95f` |
| API | `sha256:2f8d0e5cc0ca07b0a5ddef78042e83f3f95707b37c4989862e1eba351c680030` |
| MCP | `sha256:b9607feba85b5765bd7b5ec0af877a6761c8cbb099d8f5c13a701e2bf9831e9c` |

`deploy/artifact-cleanup-policy.json` remains attached with dry-run enabled:

- delete untagged versions older than seven days;
- keep the ten most recent versions of each package.

Review the cleanup audit before enabling deletion.

## Enabled service APIs

- Cloud Run;
- Cloud SQL Admin;
- Artifact Registry;
- Cloud Build;
- Secret Manager;
- Cloud Billing Budgets;
- IAM, Logging, Monitoring, Compute, and Resource Manager dependencies.

## Runtime resources

| Resource | Verified state |
|---|---|
| `command-center-postgres` | PostgreSQL 16, `db-f1-micro`, zonal `me-west1`, 10 GB SSD, backups on, storage growth off, connector-only, deletion protection on |
| `command-center-db-migrate` | app-role migration 6 job; final execution `command-center-db-migrate-vxbwf` succeeded |
| `command-center-api` | revision `command-center-api-00005-q89`, 100% traffic |
| `command-center-mcp` | revision `command-center-mcp-00005-p6n`, 100% traffic |
| `command-center-web` | revision `command-center-web-00004-lz7`, 100% traffic |

Judge URL:
`https://command-center-web-67134152472.me-west1.run.app`.

Remote MCP URL:
`https://command-center-mcp-67134152472.me-west1.run.app/mcp`.

The runtime identities are `command-center-web`, `command-center-api`, and
`command-center-mcp`. Web has neither Cloud SQL nor Secret Manager access. API
and MCP have Cloud SQL Client; secret access is bound per named secret. The
active inventory is `COOKIE_SECRET`, `PROVIDER_CREDENTIAL_SECRET`,
`DEMO_ACCESS_CODE`, and `COMMAND_CENTER_DATABASE_URL`. There is no operator
`OPENAI_API_KEY`. The disabled one-time database administrator secret has no
runtime accessor.

## Verified staging receipts

- same-origin login sets a Secure, HttpOnly, SameSite=Lax cookie;
- unauthenticated API and MCP calls return 401;
- GitHub Actions run `29679958610` passed Python 3.12, Node 22, backend and
  web tests, retrieval evaluation, production build, and the security scan;
- production accepts a canonical encrypted BYOK envelope and rejects the same
  envelope with appended noncanonical data; the synthetic credential was
  deleted immediately after this regression check;
- API and MCP expose identical ten-tool schemas;
- all ten MCP tools were called through the hosted service;
- Taste version 1 is the primary redesign recommendation with content hash
  `e5683393fbe3d0e7bf412e22e0a83f68b88e01d015e48fd4481b559eee6d06e5`;
- screenshot hash `02d7009ecc32da0d48eaf16d64778a72bd030933d50cb9ad84ce9f5b11e6feef`
  records 375×812 dimensions, labelled inferences, degraded no-key analysis,
  and `retained=false`;
- handoff `hoff_c5b352d8a5734882` persisted a seven-step deterministic Taste
  plan, published, loaded through MCP, and remained immutable;
- post-restart activation `activate_ddb1a366bec14d41` loaded the same handoff;
- architecture snapshot `asnap_cf2e8d0c7682d2ea1606ce84` has 26/26 valid
  cards, 100% dense coverage, zero issues, and the release image revision;
- token revocation returned 401 and fresh browser pairing restored MCP access;
- a synthetic BYOK envelope was isolated from a second workspace and deleted;
- all synthetic pending memory proposals were rejected, leaving zero durable
  memories and zero pending proposals;
- after forced fresh revisions of all three services, cookies, tokens,
  architecture, and handoffs remained durable through PostgreSQL;
- the final revisions produced no Cloud Logging error entries during the
  staging run.

## Remaining continuation order

1. Complete the real Taste interview and user-approved Handoff Builder +
   Guided Tour redesign without inventing the design answers.
2. Capture 375, 768, 1024, and 1440 pixel browser receipts, keyboard/focus,
   reduced-motion, touch-target, empty/error/loading, and live Realtime checks.
3. Reinstall the cachebusted v0.5 plugin on clean Linux, start a fresh Codex
   thread, load the published handoff visibly, and capture `/feedback`.
4. Promote to v1.0 only after those gates pass; rebuild and deploy the exact
   promoted artifact.
5. Record and verify the human-narrated sub-three-minute YouTube video, complete
   the human-authored Devpost copy, and submit before the deadline.
