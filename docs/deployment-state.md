# Deployment state and continuation receipt

```yaml
ai_card:
  id: command-center.deployment-state
  repository: Command Center
  title: Deployment State and Continuation Receipt
  kind: operations_receipt
  audience: [operator, engineer, ai_agent]
  status: active
  owner_area: cloud deployment
  main_files: [cloudbuild.three-service.yaml, deploy, docs/cloud-run.md, docs/deployment-topology.md]
  public_interfaces: [Google Cloud project, Artifact Registry, staging continuation gate]
  provides: [idempotent deployment continuation, current external resource state]
  depends_on: [command-center.deployment-topology, command-center.cloud-run]
  safe_edit_points: [append verified resource receipts after successful commands]
  risk_areas: [duplicating resources, deploying unreconciled source, unbounded Cloud SQL spend]
  graph_rag_entities: [Google Cloud, Artifact Registry, Cloud Run, Cloud SQL]
  last_verified: 2026-07-19
```

This card records external state that was verified from the Termux deployment
environment. It is a continuation receipt, not a claim that staging or
production is deployed.

## Verified Google Cloud target

| Field | Value |
|---|---|
| Project ID | `codex-command-centet` |
| Project number | `67134152472` |
| Shared region | `me-west1` |
| Billing | enabled |
| Release feature commit | `b8ed8ffedd294d077e22cb0af416af6c0b32aff9` |
| Release branch | `termux/taste-byok-deployment` |

The project ID intentionally ends in `centet`; do not “correct” it in commands.
Cloud Run, Cloud SQL for PostgreSQL, and Artifact Registry are available in the
selected Tel Aviv region.

## Existing resources

Artifact Registry contains one standard Docker repository:

```text
projects/codex-command-centet/locations/me-west1/repositories/command-center
```

At verification time its stored size was `0.000 MB`. It has no images.
`deploy/artifact-cleanup-policy.json` is attached with dry-run enabled:

- delete untagged versions older than seven days;
- keep the ten most recent versions of each package.

The dry run must remain enabled until real staging images exist and the
resulting policy audit is reviewed.

## Enabled service APIs

- Cloud Run;
- Cloud SQL Admin;
- Artifact Registry;
- Cloud Build;
- Secret Manager;
- IAM, Logging, Monitoring, Compute, and Resource Manager dependencies.

## Resources that do not exist yet

- no Cloud Build has been submitted for the three service images;
- no Cloud SQL instance or database has been created;
- no Cloud Run web, API, or MCP service has been deployed;
- no production secret values or runtime service accounts have been created;
- no custom domain, load balancer, budget alert, or production traffic exists.

## Required continuation order

1. Reconcile the laptop-only dense architecture retrieval commit with the
   pushed Termux branch without discarding either line of work.
2. Rerun Python, web, plugin, architecture, security, and PostgreSQL contract
   gates on the reconciled commit.
3. Submit `cloudbuild.three-service.yaml` with `_IMAGE_TAG` set to that exact
   commit SHA.
4. Select an explicitly bounded Cloud SQL tier and storage budget before
   creating the instance.
5. Create separate web, API, and MCP runtime service accounts and bind only
   required Cloud SQL and named-secret permissions.
6. Create cookie, BYOK-envelope, access-policy, and database connection secrets.
   Never create an operator `OPENAI_API_KEY` secret.
7. Run the database release/migration job, deploy API and MCP, then configure
   the web proxy with the API `run.app` origin.
8. Execute all staging gates from
   [Three-service deployment topology](deployment-topology.md) before any
   production promotion.
