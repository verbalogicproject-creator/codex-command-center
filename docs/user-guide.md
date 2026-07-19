# User guide

```yaml
ai_card:
  id: command-center.user-guide
  repository: Command Center
  title: Complete User Guide
  kind: user_manual
  audience: [user, evaluator, ai_agent]
  status: implemented
  owner_area: product documentation
  main_files: [apps/web/app/page.tsx, services/memory/aria_memory/app.py, plugins/codex-command-center]
  public_interfaces: [Aria, Capability Library, Handoff Builder, Knowledge Graph, Codex plugin]
  provides: [complete operating model from startup through inspected handoff]
  depends_on: [command-center.architecture-awareness, command-center.security-privacy]
  safe_edit_points: [documented browser and plugin workflows]
  risk_areas: [confusing proposals with durable memory, skipping repository verification]
  graph_rag_entities: [UserWorkflow, Aria, Codex Command Center]
  last_verified: 2026-07-19
```

Command Center answers two practical questions: **what context did the coding
agent use, and how can a reviewed plan continue in Codex without losing its
toolbox?**

You do not need to understand retrieval systems to use it. The interface uses
four ideas:

1. **Architecture awareness** versions how a repository works: subsystems,
   interfaces, dependencies, safe edit points, risks, and source receipts.
2. **Durable memory** records what happened or was decided as facts and
   episodes.
3. **A capability** is a versioned, provider-neutral workflow or policy.
4. **A handoff** pins one Open Plan, exact capability versions, and a bounded
   evidence packet for Codex.

## The fastest tour

1. Sign in and select **Tour**, or select the floating Aria microphone and say
   **“Start the guided tour.”**
2. Select **New synthesis**.
3. Choose **Explore the private mobile stack** or type a question.
4. Expand **Context packet injected** under Aria’s response.
5. Expand **Shared architecture awareness** and inspect repository, snapshot,
   revision, coverage, selected versioned sources, interfaces, safe edit points,
   risks, omissions, and degraded state.
6. Select any source to open the original evidence.
7. Open **Knowledge Graph**. Violet nodes are declared structure, amber nodes are
   durable memory, and cyan highlights plus animated edges show the active packet.
8. Ask Aria to “Propose a decision.” A pending proposal appears.
9. Confirm or reject it in the browser. Voice Aria, text Aria, and Codex cannot confirm their own
   writes.
10. Reload the page. The session, turns, and proposal return from storage. A
   confirmed write appears in Timeline and Audit.

## Prepare for Codex

Before the first handoff for a checkout, pair the plugin and explicitly run
`architecture.py lint .`, `status .`, then `sync .`. Sync shows the exact
manifest-selected Markdown and asks before upload. Session hooks never perform
that upload.

Open **Handoff Builder** and choose a repository. Upload or paste a screenshot,
describe the desired change, and select **Analyze and prepare for Codex**.
Alternatively, ask text Aria for a frontend redesign and use its exact
**Prepare in Handoff Builder** suggestion.

The builder separates:

- Sol’s screenshot-derived inferences;
- the primary workflow and visible alternatives;
- an editable Open Plan;
- the Sol or deterministic planning receipt and degradation reasons;
- exact evidence included and candidates omitted;
- pinned architecture snapshot, revision, coverage, and source hashes;
- safe edit points and risks;
- the exact packet and Codex command.

Raw screenshot bytes are not retained or sent into plan/tour generation.
Review the plan and select or say the exact phrase
**Approve this handoff.** Publication makes the bounded packet
available to paired clients, but performs no code or external action.

Published handoffs are immutable. If the plan changes, create a new version.
Copy the generated `/plan Load Command Center handoff <ID> and interview me
before editing.` command into Codex. The first Codex action should be a visible
`load_handoff` call, followed by an evidence-citing summary and interview
question.

A later architecture sync improves new briefs without changing the published
handoff. Codex can load a registered checkout alias, but an unrelated or
unknown repository fails closed.

## Capability Library

Open **Toolbox** to inspect capability kind, version, triggers, compatible
repositories, required tools, trust, provenance, content hash, and recent
activations. Only verified and workspace-trusted latest versions are recommended
for new handoffs. An existing handoff continues to reference the exact version
it pinned.

## Voice navigation

Select the floating microphone orb to start an OpenAI Realtime session. Aria can
navigate all seven surfaces, scroll, open cited evidence, run recall, focus the
graph, switch Deep Synthesis, control either guided-tour mode, start and prepare
a redesign session, select a visible trusted workflow, edit the Open Plan, open
the packet, and create pending proposals. It may publish only after the exact
phrase “Approve this handoff.” Say “stop” to interrupt an answer or select the square
button to close the microphone session.

Voice is an optional control layer. The button-driven tour and every ordinary
surface remain available when no OpenAI key or microphone is present. See the
[complete voice guide](aria-voice.md) for commands, setup, privacy, and
troubleshooting.

## Reading a context packet

The packet header shows `used / budget` estimated tokens. This is a conservative
bound, not a model tokenizer bill.

Each source has a stable ID, its entity class and repository, and selection
reasons such as lexical, structural, dense, or declared. The API response also
contains individual signal and named-dimension contributions.

The packet says how many lower-ranked candidates were omitted. “Omitted” does not
mean irrelevant; it means they did not fit the current bounded selection. If
dense embeddings are unavailable, the packet says **degraded fallback** and
continues with lexical, structural, and declared signals.

## What the graph colors mean

| Color | Meaning |
|---|---|
| Violet | Repository and declared AI-card structure |
| Cyan | Sources active in the current injected packet |
| Amber | Human-authored or human-confirmed durable memory |
| Animated edge | Exact evidence relationship active in this session |

On a phone, the graph defaults to the active packet and its immediate
relationships. This avoids presenting the entire corpus as an unreadable map.
Select a node to open its original evidence record. The moving particle is
decorative confirmation of the active relationship; with reduced motion enabled,
the same state remains visible through cyan cards and edges.

The bottom dock can be swiped or dragged continuously. Keyboard users can use
Tab to enter the dock and the left or right arrow keys to move between its five
surfaces.

## Writes and refusals

“Propose” never means “save.” It creates a persisted `pending` proposal. Only the
authenticated Confirm button executes a durable operation.

The MUD guard refuses merge decisions that conflict with active project-boundary
evidence. A refusal is visible on the proposal card, recorded in Audit, and
survives reload. No memory row is created.

## Data boundaries

- The public corpus contains only synthetic memories and sanitized technical
  AI cards.
- Repository source URIs are relative. Absolute machine paths are rejected.
- Prompts are sent in POST bodies, never query strings.
- Hook telemetry accepts only a small declared field set. Raw prompts and tool
  outputs are not durable telemetry.
- Local workspaces use isolated SQLite databases. Hosted production workspaces
  must use durable Cloud SQL rather than an instance filesystem.

## Common questions

**Why did a source rank highly?**

Open the packet and read its selection reasons. The document API also exposes
lexical, structural, dense, declared, and named-dimension contributions.

**Did the agent scan the whole repository?**

The context packet starts from predeclared repository cards and persistent
indexes. The retrospective evaluation records zero repository reads for the
injected path.

**Can I use the system without an OpenAI key or NumPy?**

Yes. The hash embedding provider and pure-Python cosine path are complete
fallbacks. The UI explicitly reports degraded model routing when no key exists.

**Where do I set up Codex?**

Select **Pair Codex** in the header, then follow the
[Codex plugin guide](codex-plugin.md). The one-time code makes Codex proposals
appear in the same isolated browser workspace.

**Can voice confirm a memory write?**

No. Aria can draft a pending proposal and move you to its review surface, but
confirmation requires an explicit authenticated browser tap.

**Can voice publish a handoff?**

Yes, after the exact phrase “Approve this handoff.” A handoff is bounded context,
not a memory write, code change, installation, deployment, or external action.
