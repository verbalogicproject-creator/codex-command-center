# Deployment and submission checklist

```yaml
ai_card:
  id: command-center.deployment-checklist
  repository: Command Center
  title: Deployment and Submission Checklist
  kind: checklist
  audience: [operator, presenter, ai_agent]
  status: active
  owner_area: deployment and submission
  main_files: [Dockerfile, cloudbuild.yaml, docs/cloud-run.md]
  public_interfaces: [Cloud Build, Cloud Run, remote MCP]
  provides: [ordered promotion and submission gates]
  depends_on: [command-center.cloud-run, command-center.postgresql-proot, command-center.eval-report]
  safe_edit_points: [marking only evidence-backed completed gates]
  risk_areas: [wrong GCP project, skipped staging handshake, mutable demo state]
  graph_rag_entities: [DeploymentGate, SubmissionGate]
  last_verified: 2026-07-18
```

- [x] Create public GitHub repository `verbalogicproject-creator/codex-command-center`.
- [x] Validate the manifest-selected Markdown corpus at 100% architecture-card
  coverage.
- [x] Run the SQLite suite, real PostgreSQL behavioral contract, clean restart,
  and repeated PostgreSQL contract.
- [ ] Build the root Dockerfile on a Docker-capable laptop or Cloud Build.
- [ ] Create Artifact Registry, Cloud SQL PostgreSQL, runtime service account,
  budget alerts, and Secret Manager secrets.
- [ ] Run Cloud Build using `cloudbuild.yaml`.
- [ ] Authenticate and execute the hero recall and Deep Synthesis.
- [ ] Confirm a proposal, reload, and inspect its audit entry.
- [ ] Expand the injected context packet and open both a document and memory source.
- [ ] Verify an attempted conflicting merge leaves a visible MUD refusal.
- [ ] Run `PYTHONPATH=services/memory python scripts/eval.py` and retain the falsification trace.
- [x] Validate all ten Codex plugin MCP tools and four hooks; verify browser
  pairing creates a pending-only proposal.
- [x] Validate trusted project-local MCP/hook registration, paired context
  injection, read/write tool annotations, and production-safe Stop behavior.
- [ ] Open a fresh Codex thread at the repository root and confirm `/mcp` and
  `/hooks` show Command Center as first-class and trusted.
- [ ] Authenticate a second browser workspace and verify isolation.
- [ ] Restart the Cloud Run revision and verify published handoffs remain
  available through Cloud SQL.
- [ ] Run a live OpenAI retrieval/agent smoke test with explicit cost limits.
- [ ] On the HTTPS deployment, start Aria voice and verify navigation, scrolling,
  recall, graph focus, barge-in, transcript state, and microphone shutdown.
- [ ] Draft a proposal by voice and verify there is no voice confirmation tool
  and no durable mutation before the authenticated browser tap.
- [x] Run secret/history scan against the final Git object database; the only
  environment-name match is the sanitized `.env.example` template.
- [ ] Sync the final commit-pinned docs into Aria and compare Aria/Codex
  snapshot receipts.
- [ ] Record a sub-three-minute narrated video.
- [ ] Submit the Cloud Run URL, public repository URL, video, and `/feedback` ID.
- [ ] Run authenticated remote MCP initialize, tools/list, handoff load, token
  revoke, cold-start, and repository-mismatch smoke tests in staging and prod.
