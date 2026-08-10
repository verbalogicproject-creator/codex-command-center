# Three-minute competition demo script

```yaml
ai_card:
  id: command-center.demo-script
  repository: Command Center
  title: Three-Minute Competition Demo
  kind: demo_script
  audience: [presenter, evaluator, ai_agent]
  status: implemented
  owner_area: submission
  main_files: [apps/web/app/page.tsx, plugins/codex-command-center]
  public_interfaces: [Handoff Builder, Aria voice, "load_handoff"]
  provides: [Codex-centered competition narrative and timing]
  depends_on: [command-center.architecture-awareness, command-center.handoffs, command-center.codex-plugin]
  safe_edit_points: [timing and narration that preserve demonstrated facts]
  risk_areas: [showing another provider, claiming deployment before verification]
  graph_rag_entities: [Aria, GPT-5.6 Sol, GPT-5.6 Luna, Codex]
  last_verified: 2026-07-20
```

## 0:00–0:15 — The continuity problem

Show the Codex plugin list with only **Codex Command Center** installed.

Narration: “AI can act, but it still loses architectural continuity and hides
what grounded the next action. I want one reviewed plan to survive the move
from Aria into Codex.”

## 0:15–0:50 — Give Aria the task

Open **Handoff Builder**, select the Command Center repository, paste the current
interface screenshot, and tell Aria what should change.

Show that raw image retention is off. Let Sol produce observations, and point to
the **Screenshot-derived inferences** label.

## 0:50–1:10 — Inspect the grounding contract

Show the primary **Taste-guided frontend redesign interview** recommendation
and its exact version/hash. Briefly reveal the visible
alternatives. Edit one Open Plan line.

Open the exact bounded grounding packet. Point to its pinned architecture
snapshot, grounding-source IDs, selection reasons, safe edit points, omissions,
and degraded state. Do not read every field.

## 1:10–1:28 — Approve by voice

Say: **“Approve this handoff.”**

Aria publishes it and reads the exact command:

```text
/plan Load Command Center handoff <ID> and interview me before editing.
```

State that voice exposed bounded context only; it did not edit code, install a
tool, deploy, or confirm memory.

## 1:28–2:08 — Continue in Codex

Open Codex in the same repository and run the generated command. Show the
visible `load_handoff` call. Pause on:

- capability ID, version, hash, and provenance;
- approved Open Plan;
- screenshot inferences;
- repository identity, pinned snapshot/revision, and evidence receipts;
- safe edit points and risks;
- activation receipt.

Codex summarizes what was injected and asks the first informed redesign
question before editing.

## 2:08–2:40 — Take a step back

Open `/atlas/index.html` and say: “Now take a step back.”

Select the featured **Published handoffs cannot silently change** receipt.
Move quickly through the visible product control, authenticated route, Python
publication policy, SQLite/PostgreSQL tables, regression test, and conflict
failure behavior.

Then select **The architecture exhibit proves its own source boundary** and
show its generator, source snapshot hash, and stale-artifact test.

Narration: “This is not a diagram drawn after the code. The explanation is
compiled from the repository it explains.”

## 2:40–2:55 — Name and origin reveal

Return to the atlas hero:

“I call it **NLKE Grounded Continuity Architecture**. Natural Language
Knowledge Engineering is the methodology; Command Center is its first public
reference implementation.”

Scroll to the timestamped June 2025 OpenAI Community artifact:

“On my first day using an LLM, before I knew the vocabulary of RAG or agent
frameworks, I discovered the same grounding principle manually. Thirteen months
later, it is an implemented architecture.”

## 2:55–3:00 — Close

End on:

> Continuity without hidden memory. Grounding without surrendered control.

Put the full `/atlas/index.html` and specification URLs in Devpost and the video
description. The product and visible Codex load remain the primary proof.

Do not show another provider in the main video.
