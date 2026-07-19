# Roadmap

```yaml
ai_card:
  id: command-center.roadmap
  repository: Command Center
  title: Command Center Roadmap
  kind: roadmap
  audience: [user, engineer, evaluator, ai_agent]
  status: active
  owner_area: product direction
  main_files: [docs/plans/full-architecture-awareness.md, docs/deployment-checklist.md]
  public_interfaces: [future compatibility and deployment milestones]
  provides: [separation of implemented verified and future work]
  depends_on: [command-center.architecture, command-center.deployment-checklist]
  safe_edit_points: [evidence-backed status transitions]
  risk_areas: [presenting future compatibility as demonstrated support]
  graph_rag_entities: [Roadmap, Command Center]
  last_verified: 2026-07-18
```

## Completed foundation

1. Typed hero workflow and durable proposal restoration.
2. Declared AI-card retrieval and context compiler.
3. Codex hooks and MCP plugin.
4. Explainable graph and packet inspector.
5. Reproducible retrospective proof, tests, and deployment.
6. Provider-agnostic UI commands, OpenAI Realtime voice transport, captions,
   interruption state, pending-only voice proposals, and a button-equivalent
   guided tour.
7. Versioned capability library, Sol screenshot analysis, immutable handoff
   lifecycle, remote MCP, revocable token pairing, and Codex Command Center
   plugin.
8. Capability Library and Handoff Builder surfaces with voice publication and
   activation receipts.
9. Shared full architecture awareness for Aria and Codex: versioned snapshots,
   bounded ArchitectureBrief, explicit sync/health, immutable handoff receipts,
   and Codex Command Center v0.5.
10. SQLite and real PostgreSQL behavioral verification, including restart and
    historical architecture evidence.

11. Deterministic redesign suggestions, persisted Sol planning receipts,
    controller-backed voice drafting, evidence-aware Luna fallback, and exact
    visible Codex handoff activation.

## Next: cloud promotion and submission

The immediate promotion phase is to push the reviewed repository, build the
root image on a Docker-capable laptop or Cloud Build, create least-privilege GCP
resources in the verified project, pass staging database/MCP/mobile/voice
smokes, and promote the same image digest for the competition demo.

Overview and redesign tours now operate live surfaces with bounded receipts and
explicit pauses. Remaining work is external production promotion, clean Codex
reinstall validation, dogfood capture, video, and submission.
