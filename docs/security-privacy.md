# Security, privacy, and approval boundaries

```yaml
ai_card:
  id: command-center.security-privacy
  repository: Command Center
  title: Security Privacy and Approval Boundaries
  kind: policy
  audience: [user, engineer, operator, ai_agent, evaluator]
  status: implemented
  owner_area: security
  main_files: [services/memory/aria_memory/app.py, services/memory/aria_memory/store.py, plugins/codex-command-center/scripts/client.py]
  public_interfaces: [browser confirmation, workspace token, pending memory proposal]
  provides: [authentication data classes approval matrix and threat checks]
  depends_on: [command-center.architecture-awareness, command-center.handoffs, command-center.byok]
  safe_edit_points: [additive restrictive validation, hashed token storage]
  risk_areas: [secret leakage, cross-repository context, model-confirmed durable writes]
  graph_rag_entities: [WorkspaceToken, PendingProposal, ApprovalBoundary]
  last_verified: 2026-07-19
```

## Authentication

Browser sessions use a signed HttpOnly, SameSite=Lax cookie. **Pair Codex**
creates a cryptographically random one-time code whose hash and five-minute
expiry are stored in the isolated workspace. Its single successful exchange
atomically marks it consumed and returns a revocable random workspace token.
The database stores only SHA-256 code and token hashes.

Direct MCP clients send the token in `X-Command-Center-Token`. Tokens never
belong in URLs, repository files, handoff bodies, hook events, screenshots, or
logs. Revocation sets a timestamp and immediately prevents token authentication.

## Data classes

| Data | Persistence |
|---|---|
| Raw screenshot bytes | Never retained |
| Visual role/label/hash/dimensions/MIME/findings/comparison groups | Handoff |
| Capability instructions and versions | Workspace database |
| Architecture manifest | Repository; paths and identities only |
| Architecture cards and sections | Versioned workspace snapshots after explicit sync |
| Draft/published/revoked handoffs | Workspace database |
| Handoff activations | Audit table |
| Facts and episodes | Durable memory table |
| Hook telemetry | Separate bounded telemetry table |
| Pairing code | Client sees it once; server stores hash, expiry, and consumption |
| Workspace token | Client filesystem; server stores hash only |
| User OpenAI API key | Authenticated encrypted browser-session cookie; never database storage |
| Realtime client secret | Browser memory for one short-lived voice connection |

OpenAI Responses requests use bounded selected evidence, a stable hashed safety
identifier, and `store: false` in the Aria agent path. Visual comparison sends
only the validated, resized current/reference/constraint images during the
analysis request and only when that workspace has an active BYOK credential.
Planning, tours, persistence, and Codex receive no raw image bytes. Failure
falls back to visibly degraded deterministic findings. The
encrypted credential cookie is bound to one workspace, scoped to `/api/v1`,
authenticated against tampering, cryptographically expired, unreadable by
browser JavaScript, and removable immediately.

## Approval matrix

| Action | Aria voice | Sol analysis | Codex MCP | Browser |
|---|---:|---:|---:|---:|
| Navigate/narrate | yes | no | no | yes |
| Draft handoff | yes | analysis only | no | yes |
| Publish bounded handoff | exact phrase | no | no | yes |
| Load published handoff | no | no | yes | yes |
| Draft memory proposal | yes | yes | yes | yes |
| Confirm durable memory | no | no | no | yes |
| Edit repository | no | no | client approval applies | no |
| Install tools/plugins | no | no | no | separate user action |
| Deploy/external action | no | no | no | separate explicit authority |

Published handoffs are immutable, repository-bound, and version-pinned.
Visual-source findings are role-labelled as inferences. Untrusted and retired
capabilities are excluded from normal selection. Optional retrieval failures
produce visible degraded metadata.

Architecture discovery is bounded by a repository manifest. Session hooks may
send hashes for drift detection but never upload document bodies. Content sync
requires an explicit helper or browser action. Unknown repositories return an
empty degraded brief; no unfiltered context fallback is allowed. A handoff may
load through a registered checkout alias only when that alias resolves to the
same canonical repository.

## Logging

The service intentionally avoids request bodies, prompt text, tokens, screenshot
bytes, access codes, and memory bodies in structured logs. Hook detail accepts
only summary, outcome, changed files, duration, exit code, and the explicit
proposal-draft switch. Run `scripts/security-scan.sh` before release.

## Threat-focused checks

- reuse of a pairing code fails;
- revoked tokens fail on REST and MCP;
- a token hash cannot authenticate;
- a published handoff cannot be patched;
- repository mismatch returns 403;
- unknown repositories never receive another repository's evidence;
- architecture traversal, symlink escape, and oversized corpora are rejected;
- later syncs do not change evidence pinned by a published handoff;
- revoked handoffs cannot load;
- unsupported screenshot MIME or corrupt bytes return 422;
- provider credentials cannot cross workspaces, survive cryptographic expiry,
  appear in API responses, or enter SQLite/PostgreSQL;
- a configured administrative embedding key cannot fund public Aria or voice;
- arbitrary hook detail is dropped;
- Codex cannot confirm a memory write.
