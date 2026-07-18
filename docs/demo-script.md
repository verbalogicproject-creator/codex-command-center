# Three-minute competition demo script

```yaml
ai_card:
  id: command-center.demo-script
  repository: Command Center
  title: Three-Minute Competition Demo
  kind: demo_script
  audience: [presenter, evaluator, ai_agent]
  status: implementation_ready
  owner_area: submission
  main_files: [apps/web/app/page.tsx, plugins/codex-command-center]
  public_interfaces: [Handoff Builder, Aria voice, "load_handoff"]
  provides: [Codex-centered competition narrative and timing]
  depends_on: [command-center.architecture-awareness, command-center.handoffs, command-center.codex-plugin]
  safe_edit_points: [timing and narration that preserve demonstrated facts]
  risk_areas: [showing another provider, claiming deployment before verification]
  graph_rag_entities: [Aria, GPT-5.6 Sol, Codex]
  last_verified: 2026-07-18
```

## 0:00–0:20 — Promise

Show the Codex plugin list with only **Codex Command Center** installed.

Narration: “Plan with Aria. Continue in Codex. Bring your toolbox everywhere.
Today GPT-5.6, Aria, and Codex will carry one inspectable redesign plan from
voice and screenshot into a coding interview.”

## 0:20–0:55 — Give Aria the task

Open **Handoff Builder**, select the Command Center repository, paste the current
interface screenshot, and tell Aria what should change.

Show that raw image retention is off. Let Sol produce observations, and point to
the **Screenshot-derived inferences** label.

## 0:55–1:30 — Inspect the toolbox

Show the primary **Frontend redesign interview** recommendation and its exact
version. Briefly reveal the mobile accessibility and evidence-plan
alternatives. Edit one Open Plan line.

Open the exact bounded packet. Point to architecture, evidence IDs and selection
reasons, pinned snapshot and source revision, architecture coverage, safe edit
points, risks, omitted candidates, token estimate, and degraded state.

## 1:30–1:50 — Approve by voice

Say: **“Approve this handoff.”**

Aria publishes it and reads the exact command:

```text
/plan Load Command Center handoff <ID> and interview me before editing.
```

State that voice exposed bounded context only; it did not edit code, install a
tool, deploy, or confirm memory.

## 1:50–2:45 — Continue in Codex

Open Codex in the same repository and run the generated command. Show the
visible `load_handoff` call. Pause on:

- capability ID, version, hash, and provenance;
- approved Open Plan;
- screenshot inferences;
- repository identity, pinned snapshot/revision, and evidence receipts;
- safe edit points and risks;
- activation receipt.

Codex summarizes what was injected, cites evidence IDs, and asks the first
redesign interview question before editing.

Briefly show the animated graph edge from the published handoff into Codex, but
keep the informed interview question as the ending.

## 2:45–3:00 — Close

Stop at the question.

Narration: “One cloud Command Center carried a reviewed toolbox into Codex
without installing arbitrary skills or hiding context. The same hosted MCP is
provider-neutral for future compatible clients, but this workflow is built
around GPT-5.6, Aria, and Codex.”

Do not show another provider in the main video.
