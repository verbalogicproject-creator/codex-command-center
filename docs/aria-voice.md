# Aria voice and guided navigation

```yaml
ai_card:
  id: command-center.aria-voice
  repository: Command Center
  title: Aria Voice and Guided Navigation
  kind: user_guide
  audience: [user, engineer, ai_agent, evaluator]
  status: implemented
  owner_area: Aria interface
  main_files: [apps/web/components/AriaVoice.tsx, apps/web/lib/aria/commands.ts, apps/web/lib/handoff-controller.ts, services/memory/aria_memory/aria_registry.py]
  public_interfaces: ["/api/v1/realtime/token", "/api/v1/aria/commands", "/api/v1/aria/profiles", "/api/v1/aria/devhub", "/api/v1/chat/stream"]
  provides: [persistent voice transport, scoped command registry, unified transcript, persona profiles, bounded DevHub receipts]
  depends_on: [command-center.architecture-awareness, command-center.handoffs, command-center.byok]
  safe_edit_points: [typed browser command router, narration after visible UI completion]
  risk_areas: [voice implying external authority, exposing standard API keys]
  graph_rag_entities: [Aria, OpenAI Realtime, GPT-5.6 Sol]
  last_verified: 2026-07-19
```

Aria is a persistent Command Center agent. Her fixed orb and WebRTC transport
remain mounted while the user moves among surfaces or starts a tour. Her Aria
home has Conversation, Voice & Persona, and DevHub tabs. It does not create a
second agent, database, context corpus, or memory service.

## Start voice

1. Sign in and select **Connect OpenAI**. Paste your own API key into the
   password field. The backend returns only an encrypted, HttpOnly,
   browser-session envelope.
2. Set optional `ARIA_REALTIME_MODEL` and `ARIA_REALTIME_VOICE` values. The
   defaults are `gpt-realtime-2.1` and `marin`.
3. Open Command Center through HTTPS or `localhost`. Browsers require a secure
   context for microphone access.
4. Select the fixed microphone orb and approve microphone access.
5. Speak naturally: “Open Handoff Builder,” “open the graph,” “focus fact cc
   zero seven,” “run recall for the approval boundary,” or “start the guided
   tour.”
6. Open Aria and select **Stop**. Microphone tracks,
   the data channel, remote audio, and the peer connection are closed together.

There is no floating transcript panel. While voice is active, the orb opens
Aria’s Conversation tab. That tab exposes listening, thinking, speaking,
muted, and error states alongside stop and reconnect controls. Typed and spoken
turns share the persisted chronological transcript and are labelled by
modality. Raw audio, SDP/WebRTC payloads, and provider credentials are never
stored.

## Registry and context projection

Migration 8 adds command definitions, profile-specific aliases, persona
profiles, voice sessions, bounded execution receipts, and turn modality.
SQLite and PostgreSQL use the same contract. Built-ins come from the versioned
repository manifest in `aria_registry.py`; workspace rows are reconciled by
stable ID and SHA-256 hash at startup. Database rows contain metadata only.
Executable handlers remain the TypeScript allow-list.

Realtime receives a deterministic subset: global navigation/tour commands,
active-surface commands, and an optional active-workflow set. Connection
includes a compact state snapshot. Navigation and drawer/tour changes produce
compact state deltas instead of replaying repository context. Surface,
workflow, profile, and alias changes refresh the effective Realtime tool
projection while the WebRTC transport remains connected.

Profiles persist voice, preset, bounded tone/directness/verbosity/initiative,
and explicitly enabled eligible commands. Active selection stays in browser
local storage. Profiles cannot change schema, handler, safety, confirmation, or
trust metadata. Alias normalization detects profile-local collisions and
reserves the handoff approval phrase. The effective command projection appends
the selected profile's permitted aliases to Realtime tool descriptions, so a
spoken alias still resolves to the same semantic command rather than a
synthetic click.

DevHub correlates bounded voice transcript events, Realtime call IDs, command
IDs, sanitized arguments/results, timing, errors, and transport degradation.
Its coverage badge is deliberately scoped to the registered Aria action
projection. It is not described as proof that every DOM control is voice
eligible. A cross-language regression gate requires every eligible Python
registry definition to match the frontend Realtime tool projection; the typed
frontend coverage test then requires an allow-listed controller handler.

## Supported interface commands

| Command | Result |
|---|---|
| `navigate_surface` | Opens Aria, Handoff, Toolbox, Recall, Graph, Timeline, or Audit |
| `approve_handoff` | Publishes the current draft only after the exact approval phrase |
| `scroll_page` | Scrolls up/down or jumps to top/bottom |
| `scroll_to` | Moves to a heading, content, composer, or results |
| `open_evidence` / `close_evidence` | Controls the evidence drawer |
| `focus_graph_node` | Opens Graph and centers a cited source |
| `fit_graph` | Fits the active packet or complete graph |
| `select_session` | Selects an exact visible session |
| `run_recall` | Opens Recall and executes a query |
| `set_deep_synthesis` | Enables or disables GPT-5.6 Sol in text Aria |
| `open_context_packet` | Expands the latest bounded packet |
| `start_redesign_session` | Opens and prefills a repository, intent, and optional target surface |
| `prepare_redesign_handoff` | Compares uploaded current/reference screenshots and creates the visible draft |
| `select_handoff_capability` | Selects a currently visible trusted exact reference |
| `edit_open_plan` | Bounded append, replace, remove, or reorder on the reversible draft |
| `open_handoff_packet` | Expands the packet and returns its receipt summary |
| `start_guided_tour` and tour controls | Drives overview or evidence-aware redesign mode |
| `draft_memory_proposal` | Creates a persisted `pending` proposal |

There is intentionally no `confirm_memory_write` voice command. Handoff
publication is allowed only for the exact phrase **Approve this handoff.** and
only exposes the already visible bounded packet. It does not authorize code,
installation, deployment, or another external action.

Stored voice sessions and voice-modality turns can be removed only after a
human types the exact phrase **Delete Aria voice history.** The default persona
profile cannot be deleted; non-default workspace profiles can.

## Trust boundary

```text
microphone
    │
    ▼
OpenAI Realtime session
    │ typed function call
    ▼
provider-agnostic command router
    │ validated UI operation
    ▼
Command Center browser
    │ settled result
    └──────────────► Aria continues speaking

draft_memory_proposal ──► pending proposal ──► explicit browser tap
                                                   │
                                                   ▼
                                             durable memory
```

The authenticated backend decrypts the workspace-bound BYOK envelope only long
enough to mint a short-lived Realtime client secret with a ten-minute maximum
lifetime. The standard API key is never returned to JavaScript. The browser
uses the ephemeral secret only to establish the WebRTC call. A stable,
privacy-preserving hash of the isolated workspace ID is sent as the OpenAI
safety identifier.

Voice tools operate only inside the authenticated browser workspace. They
cannot bypass proposal validation, the MUD guard, workspace isolation, or the
append-only audit trail. A voice-created proposal includes the current evidence
IDs and appears in the same review card as a Codex or text-Aria proposal.

Text Aria emits a versioned `architecture_brief` SSE event before the answer.
The browser displays repository, snapshot, revision, coverage, receipts,
interfaces, safe edit points, risks, omissions, and degraded reasons beside the
separately labelled durable ContextPack. Sol receives both bounded objects.
Voice may explain or navigate this state but cannot run architecture sync.
For frontend redesign intent, text Aria also emits
`command-center-redesign-suggestion-v1`: repository identity, exact Taste
version/hash, alternatives, selection reasons, architecture snapshot, evidence
IDs, degradation state, and a **Prepare in Handoff Builder** action.

For a comparison redesign, voice opens the session and labels the target
surface, but the user uploads or pastes the current and reference images.
`prepare_redesign_handoff` operates only after both visible slots are filled.
Aria may edit the reversible plan and explain `preserve`, `adopt`, `avoid`,
`conflicts`, and `unresolved`; it cannot fabricate a missing source or upload
one. Comparison handoffs constrain Codex to at most three focused interview
questions before its implementation plan.

This follows OpenAI’s current guidance to use WebRTC for browser Realtime
sessions, keep transport separate from business logic, and return function
outputs before asking the model to continue:

- [Voice agents](https://developers.openai.com/api/docs/guides/voice-agents#build-a-speech-to-speech-voice-agent)
- [Realtime WebRTC](https://developers.openai.com/api/docs/guides/realtime-webrtc)
- [Realtime function calling](https://developers.openai.com/api/docs/guides/realtime-conversations#function-calling)

## Guided tour

“Start the guided tour” opens an accessible visual card and moves through:

1. Aria and bounded evidence answers.
2. Recall and inspectable retrieval signals.
3. The declared/active/durable graph.
4. Sessions versus durable chronology.
5. The human approval and audit boundary.

Redesign mode comes from `POST /api/v1/tours/script`. Luna uses
`ARIA_TOUR_MODEL=gpt-5.6-luna`, `store:false`, the user's BYOK credential, and
bounded receipts—never raw screenshot bytes. The validated seven-step script
covers the problem, non-retention boundary, Taste choice, receipts, editable
plan/interview boundary, publication, and Codex activation edge.

Back, Next, Repeat, and Stop are available as 44-pixel button targets. Starting
a tour changes visual focus without disconnecting voice, restores focus when stopped,
respects reduced motion, and falls back to a deterministic evidence-bound
script without BYOK or Realtime.

## Troubleshooting

**Aria says a provider credential is required.**

Select **Connect OpenAI** in the Command Center header and provide your own API
key. If the session expired, reconnect it. Do not place the key in a repository,
URL, `NEXT_PUBLIC_` variable, or Cloud Run environment variable.

**The browser does not ask for microphone access.**

Use HTTPS or `localhost`, check the site’s microphone permission, and verify
that no other browser policy blocks `getUserMedia`.

**Voice connects but an interface command fails.**

The model receives a structured failure result and should explain it. Source
and session commands require exact IDs visible in the current workspace.

**OpenAI is unavailable.**

Text Aria, local hybrid retrieval, the graph, proposals, and the button-driven
guided tour continue to work. Only live speech is unavailable.

## Verification

Automated checks:

```sh
pytest
npm --prefix apps/web run typecheck
npm --prefix apps/web run test
npm --prefix apps/web run build
```

Manual mobile smoke test:

1. Start voice and say “start the guided tour.”
2. Use “next,” “back,” and “stop.”
3. Say “run recall for human-gated writes.”
4. Say “open evidence fact cc zero seven,” then “close evidence.”
5. Say “open the graph and fit active context.”
6. Draft a proposal and verify it remains pending until a browser tap.
7. Prepare a draft, say “Approve this handoff.” and verify the exact Codex
   command appears while durable memory remains unchanged.
8. Interrupt Aria while she is speaking, then stop the session and verify the
   browser microphone indicator turns off.
