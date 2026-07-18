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
  main_files: [apps/web/components/AriaVoice.tsx, apps/web/lib/aria/commands.ts, services/memory/aria_memory/agent.py]
  public_interfaces: ["/api/v1/realtime/token", "/api/v1/chat/stream", "architecture_brief SSE event"]
  provides: [voice navigation guide, screenshot planning workflow, voice approval boundaries]
  depends_on: [command-center.architecture-awareness, command-center.handoffs]
  safe_edit_points: [typed browser command router, narration after visible UI completion]
  risk_areas: [voice implying external authority, exposing standard API keys]
  graph_rag_entities: [Aria, OpenAI Realtime, GPT-5.6 Sol]
  last_verified: 2026-07-18
```

Aria voice is an optional control layer for the existing Command Center
interface. It does not create a second agent or a second memory service. The
same typed commands work whether they come from OpenAI Realtime, a future voice
provider, tests, or a visible browser control.

## Start voice

1. Configure `OPENAI_API_KEY` on the server. Never expose it through a
   `NEXT_PUBLIC_` variable.
2. Set optional `ARIA_REALTIME_MODEL` and `ARIA_REALTIME_VOICE` values. The
   defaults are `gpt-realtime-2.1` and `marin`.
3. Open Command Center through HTTPS or `localhost`. Browsers require a secure
   context for microphone access.
4. Select the floating microphone orb and approve microphone access.
5. Speak naturally: “Open Handoff Builder,” “open the graph,” “focus fact cc
   zero seven,” “run recall for the approval boundary,” or “start the guided
   tour.”
6. Select the square button or close the voice panel to stop. Microphone tracks,
   the data channel, remote audio, and the peer connection are closed together.

The panel exposes listening, thinking, speaking, and error states. It also
shows available input and output transcripts. The interface respects the
operating system’s reduced-motion preference.

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
| `start_guided_tour` and tour controls | Drives the five-step visual tour |
| `draft_memory_proposal` | Creates a persisted `pending` proposal |

There is intentionally no `confirm_memory_write` voice command. Handoff
publication is allowed only for the explicit phrase **Approve this handoff** and
only exposes the already visible bounded packet. It does not authorize code,
installation, deployment, or another external action.

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

The authenticated backend mints a short-lived Realtime client secret with a
ten-minute maximum lifetime. The standard API key stays on the server. The
browser uses the ephemeral secret only to establish the WebRTC call. A stable,
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

The same Back, Next, and Stop actions are available as buttons. The tour does
not require voice and remains useful when Realtime is unavailable.

## Troubleshooting

**Aria says an API key is required.**

Set `OPENAI_API_KEY` in the server or Cloud Run secret environment. Reloading
the frontend is not enough because the token endpoint runs in FastAPI.

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
7. Prepare a draft, say “Approve this handoff,” and verify the exact Codex
   command appears while durable memory remains unchanged.
8. Interrupt Aria while she is speaking, then stop the session and verify the
   browser microphone indicator turns off.
