# Bring your own model key

```yaml
ai_card:
  id: command-center.byok
  repository: Command Center
  title: Bring Your Own Model Key
  kind: security_contract
  audience: [user, operator, engineer, ai_agent]
  status: implemented
  owner_area: authentication and model routing
  main_files: [services/memory/aria_memory/credentials.py, services/memory/aria_memory/app.py, services/memory/aria_memory/agent.py, apps/web/app/page.tsx]
  public_interfaces: [provider credential session, Aria, Sol screenshot analysis, Realtime token]
  provides: [user-funded model access, non-persistent encrypted credential boundary]
  depends_on: [command-center.security-privacy, command-center.deployment-topology]
  safe_edit_points: [credential envelope module, authenticated credential endpoints, model client factory]
  risk_areas: [plaintext persistence, browser storage, key logging, operator-funded public usage]
  graph_rag_entities: [BYOK Session, OpenAI API Key, Credential Envelope]
  last_verified: 2026-07-19
```

The public Command Center deployment uses bring-your-own-key model access.
The operator's personal OpenAI API key is not the funding or authentication
boundary for public Aria, Sol, screenshot analysis, embeddings, or Realtime.

Command Center remains useful without a model key:

- declared architecture parsing and versioned snapshots;
- lexical and offline hash retrieval;
- capability recommendation;
- handoff creation, publication, loading, and audit;
- MCP initialize, tool discovery, evidence, dependency, and timeline tools;
- pending human-reviewed memory proposals.

Aria chat and screenshot analysis visibly degrade to local evidence behavior
until the user supplies a credential. Voice returns
`provider_credential_required` because a Realtime session cannot be created
offline.

## Initial credential contract

The first production release uses a non-persistent session credential:

1. An authenticated user submits an OpenAI API key to the backend over HTTPS.
2. The backend validates only enough to reject malformed input; it does not send
   the key to analytics, telemetry, or logs.
3. The backend encrypts the key into an authenticated, expiring credential
   envelope and returns it only as an HttpOnly, Secure, SameSite cookie.
4. Browser JavaScript cannot read the envelope. `localStorage`,
   `sessionStorage`, IndexedDB, service-worker caches, URLs, and client logs
   never contain the key.
5. The backend decrypts the key only for the current user's outbound OpenAI
   request.
6. The plaintext key is never stored in PostgreSQL, SQLite, handoffs, memory,
   architecture snapshots, MCP packets, audit details, or error bodies.
7. Clearing the credential or allowing the session to expire removes access.

The envelope encryption key is a Command Center service secret. It protects
opaque user-provided ciphertext; it is not an OpenAI credential and cannot fund
model usage by itself.

## API shape

The implemented authenticated endpoints are:

| Route | Behavior |
|---|---|
| `POST /api/v1/provider-credentials/openai` | Set a short-lived encrypted session key |
| `GET /api/v1/provider-credentials/openai/status` | Return configured/expiry state only |
| `DELETE /api/v1/provider-credentials/openai` | Clear the encrypted session credential |

Responses never echo the key, ciphertext, prefix, or request headers. Status
reports only provider, configured state, cryptographic expiry, and the
`encrypted_browser_session` persistence class.

## Model routing

Aria, Sol screenshot analysis, and Realtime ephemeral-token creation resolve a
credential from the authenticated request context. They do not read a global
operator key. The envelope cookie is restricted to `/api/v1`, so it is not sent
to the remote MCP route or static assets.

Hosted retrieval defaults to provider-neutral hash embeddings. An operator may
explicitly configure `EMBEDDING_PROVIDER=openai` and `EMBEDDING_API_KEY` for a
controlled indexing environment, but that administrative credential is not a
fallback for Aria, Sol, or Realtime and is not part of the public BYOK flow.

The stdio and remote MCP retrieval tools do not require an OpenAI key when hash
retrieval is active. A future MCP tool that triggers model inference must use an
explicit client credential flow rather than embedding credentials in handoffs
or MCP arguments.

## Failure behavior

- Missing key: voice returns `provider_credential_required`; Aria and screenshot
  analysis remain active with visibly degraded local results.
- Invalid/revoked key: return a sanitized provider-authentication error; never
  include upstream request headers or bodies.
- Envelope tampering, workspace mismatch, or expiry: treat the credential as
  absent; the user can replace or clear the cookie from the credential panel.
- OpenAI outage or quota exhaustion: expose degraded model routing without
  corrupting snapshots, handoffs, or memory.
- Cookie/encryption-key rotation: support a bounded previous-key grace window or
  intentionally require users to enter their keys again.

## Production gates

- automated redaction tests cover responses, cookies, database files, request
  scoping, expiry, tampering, and workspace binding;
- frontend tests prove no Web Storage or URL persistence;
- API tests prove the cookie is HttpOnly, SameSite=Lax, `/api/v1`-scoped,
  cryptographically expiring, non-persistent across a normal browser session,
  and deletable; deployed HTTPS verifies the Secure flag;
- two workspaces cannot use or infer each other's credential;
- API and MCP remain functional in offline/hash mode without any model key;
- Realtime receives only a short-lived ephemeral token, never the user's raw
  key;
- the production Secret Manager inventory contains no operator
  `OPENAI_API_KEY`.

Persistent “remember my key” support is out of scope for the first deployment.
If added later, it requires explicit opt-in, Cloud KMS envelope encryption,
ciphertext-only PostgreSQL storage, deletion/audit controls, and a separate
security review.

## Implementation receipts

- `services/memory/aria_memory/credentials.py` owns authenticated encryption,
  workspace binding, tamper rejection, and expiry.
- `services/memory/aria_memory/app.py` owns the three authenticated endpoints
  and passes plaintext only as a request-scoped function argument.
- `services/memory/aria_memory/agent.py` and `toolbox.py` have no global model
  credential fallback.
- `apps/web/app/page.tsx` clears the password input after connection and exposes
  configured, expiry, and immediate-removal controls.
- `services/memory/tests/test_credentials.py` proves encryption, expiry,
  workspace isolation, deletion, database non-retention, response redaction,
  and request-scoped Sol/Aria injection.
