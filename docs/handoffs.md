# Handoff lifecycle reference

```yaml
ai_card:
  id: command-center.handoffs
  repository: Command Center
  title: Handoff Lifecycle
  kind: domain_contract
  audience: [user, engineer, ai_agent, evaluator]
  status: implemented
  owner_area: task handoff
  main_files: [services/memory/aria_memory/toolbox.py, apps/web/app/page.tsx]
  public_interfaces: [Handoff, HandoffPacket, PlanningReceipt, "load_handoff"]
  provides: [draft publication revocation and activation semantics, immutable architecture pinning, Sol Open Plan receipts]
  depends_on: [command-center.architecture-awareness, command-center.capability-authoring]
  safe_edit_points: [draft edits, new immutable lineage versions, per-client activation audit]
  risk_areas: [editing published packets, repository mismatch, mutable evidence receipts]
  graph_rag_entities: [Handoff, HandoffPacket, HandoffActivation]
  last_verified: 2026-07-19
```

A handoff is a reusable, inspectable task artifact. It is separate from durable
memory and contains no arbitrary executable code.

```text
draft ──publish──► published ──revoke──► revoked
  │                    │
  └──edit in place     └──edit request──► new draft version
```

## Draft

The builder compiles repository identity, original intent, screenshot metadata
and findings, exact capability versions, an Open Plan, declared architecture,
ranked evidence receipts, safe edit points, risks, available tool references,
token estimate, omitted-candidate count, degraded-state metadata, and a
persisted `command-center-planning-receipt-v1`.

Sol receives only original intent, labelled screenshot findings plus
hash/dimensions, exact Taste instructions, the bounded ArchitectureBrief,
evidence IDs, safe edit points, and risks. Its result must validate as 1–12
non-empty steps of at most 500 characters. With no BYOK credential or on model
or validation failure, the builder uses the deterministic Taste plan and
records the reason. Raw screenshot bytes never enter planning.

The declared architecture member is the complete bounded
`command-center-architecture-brief-v1` selected when the draft is created. Its
snapshot ID, revision, document/section version IDs, hashes, selection reasons,
health, omissions, and degraded reasons are part of the handoff.

Raw screenshots are validated and resized in memory. The stored record contains
only SHA-256 hash, original and analyzed dimensions, MIME type, and derived
findings. The current implementation always reports `retained=false`, even if a
caller requests retention.

Drafts are editable. Changing a selected capability resolves and pins its exact
trusted version. The packet preview is the data Codex will receive.

## Publication

Publication requires the explicit browser action or exact voice phrase
**Approve this handoff.** Voice may perform it because publication only exposes bounded
context. Voice still cannot edit code, install tools, deploy, perform external
actions, or confirm durable memory.

Published records are immutable. A direct patch returns HTTP 409. Editing a
published handoff through the versions endpoint creates a new draft with the
same lineage and the next version. A newer architecture sync does not mutate an
older packet: its historical evidence IDs remain resolvable. Previous versions
remain inspectable.

## Activation

`load_handoff` accepts a handoff ID and active repository. It fails unless the
handoff is published. Exact registered IDs, names, and declared checkout
aliases are accepted; unrelated or unknown repositories fail closed with no
unfiltered fallback. Every successful load records a distinct activation ID,
client name, optional session ID, repository, evidence IDs, and timestamp.

The returned packet includes:

- exact workflow instructions, versions, hashes, and provenance;
- approved Open Plan;
- planning model, exact capability receipt, architecture snapshot, evidence
  IDs, generation time, and degradation reasons;
- pinned architecture snapshot and source revision;
- screenshot observations marked `classification=inference`;
- declared architecture;
- selected memory/document receipts and selection reasons;
- safe edit points and risks;
- available tools;
- explicit degraded reasons;
- `interview_required=true`.

Missing optional dense retrieval does not make the handoff unavailable.
`degraded=true` and a human-readable reason remain in the packet. Lower-ranked
omissions are counted instead of silently disappearing.

## Revocation

Revocation prevents new loads. Existing activation receipts and the handoff
record remain available for audit. Revocation does not delete memories,
capabilities, repository documents, or prior client session data.

## Command

Every handoff exposes the exact command:

```text
/plan Load Command Center handoff <ID> and interview me before editing.
```

The ID is not a bearer secret. Authentication still requires the paired
workspace token, and repository verification still applies.
