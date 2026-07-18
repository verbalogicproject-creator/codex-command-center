# Retrieval evaluation

```yaml
ai_card:
  id: command-center.eval-report
  repository: Command Center
  title: Reproducible Evaluation
  kind: evaluation
  audience: [engineer, evaluator, ai_agent]
  status: verified
  owner_area: quality
  main_files: [scripts/eval.py, fixtures/demo/context-eval.json, services/memory/tests]
  public_interfaces: [context evaluation harness, architecture behavioral suite]
  provides: [reproducible retrieval and handoff quality measurements]
  depends_on: [command-center.declared-context, command-center.architecture-awareness]
  safe_edit_points: [synthetic evaluation corpus, additive evidence-backed metrics]
  risk_areas: [non-reproducible model comparisons, unsupported quality claims]
  graph_rag_entities: [Evaluation, ContextPack, ArchitectureBrief]
  last_verified: 2026-07-18
```

Run on 2026-07-18 with Python 3.14 on the supplied Android/Termux environment.
The public evaluation set contains 35 labelled exact, paraphrase, cross-project,
chronology, decision, architecture and constraint queries over 46 records.

| Configuration | Recall@5 | MRR | p50 | p95 |
|---|---:|---:|---:|---:|
| Lexical score | 97.1% | 0.910 | 4.58 ms | 4.91 ms |
| Cached hash hybrid | 100% | 0.913 | 4.58 ms | 4.91 ms |

The deterministic hybrid gained 2.9 percentage points in Recall@5 on semantic
aliases while preserving exact recall. Initial indexing wrote 46 vectors;
ordinary queries wrote zero document embeddings. Coverage was 100%.

These numbers are a reproducible engineering smoke evaluation, not a production
quality claim. A live OpenAI comparison is intentionally not fabricated because
no API credential was supplied. With `OPENAI_API_KEY` and
`EMBEDDING_PROVIDER=openai`, use the same labelled fixture and record API calls,
latency and cost separately before submission.

Reproduce:

```sh
PYTHONPATH=services/memory python scripts/eval.py
```

## Declared-document mode comparison

The same script runs three public context tasks:

| Mode | Recall@5 | MRR | Median |
|---|---:|---:|---:|
| Lexical | 100% | 1.000 | 3.44 ms |
| Declared + structural | 100% | 0.667 | 3.32 ms |
| Cached hash dense | 66.7% | 0.444 | 3.96 ms |
| Full hybrid | 100% | 0.500 | 3.80 ms |

This tiny set is a falsification smoke test, not evidence that lexical retrieval
is generally superior. It shows why every signal remains visible: declared and
dense expansion can improve breadth while moving an exact target lower. Larger
labelled evaluation is required before retuning fusion weights.

## Retrospective proof

[`context-eval.json`](../fixtures/demo/context-eval.json) declares three exact
tasks, required evidence IDs, and a falsification statement for each. The
evaluation compares a full-corpus scan with one injected packet.

| Task | Full-corpus tokens | Packet tokens | Reduction | Repository reads | Missing required evidence |
|---|---:|---:|---:|---:|---:|
| Private mobile architecture | 2,585 | 1,704 | 34.1% | 5 → 0 | 0 |
| Approval boundary | 2,585 | 1,869 | 27.7% | 5 → 0 | 0 |
| Dense outage fallback | 2,585 | 1,721 | 33.4% | 5 → 0 | 0 |

The packet path records one tool call,
`POST /api/v1/context/pack`. The baseline records reading all five AI cards and
scanning the durable-memory corpus. Both paths count zero unsupported claims
because this test measures evidence retention rather than generating free-form
answers. The runnable assertion fails if any required source ID is absent.

This proves bounded evidence retention and reduced rescanning for the declared
tasks. It does not prove lower end-to-end model latency, answer quality on unseen
tasks, or production OpenAI embedding quality.

## Capability-handoff evaluation

Use one frozen redesign request, repository revision, screenshot hash, model
snapshot, and interview rubric. Run three conditions in new Codex threads:

1. **No Command Center:** request and screenshot only.
2. **Ordinary memory:** request plus bounded facts/episodes, without capability
   instructions or Open Plan.
3. **Complete handoff:** request, screenshot inferences, exact workflow version,
   approved Open Plan, architecture, evidence receipts, safe edit points, risks,
   tools, omissions, and degraded metadata.

Record:

| Measure | Collection rule |
|---|---|
| Repository reads | Count file reads before a useful plan |
| Searches | Count repository search calls before interview |
| Injected tokens | Use the same conservative estimator in all conditions |
| Time to useful plan | Start at prompt submission; stop at rubric pass |
| Evidence retained | Required evidence IDs present / required IDs |
| Unsupported claims | Claims with no screenshot-inference or evidence receipt |
| Interview quality | Blind 0–2 score for goal, preservation, responsive, accessibility, and acceptance questions |

The complete handoff passes only if it retains all required evidence, clearly
labels visual inferences, cites exact capability/evidence versions, asks before
editing, and does not increase unsupported claims. Report raw per-run traces,
median, range, model/version, repository commit, and activation ID. Do not
publish a performance claim from a single demo run.

Automated contract coverage currently verifies packet bounds, exact capability
pins, screenshot non-retention, publication immutability, repository mismatch,
activation receipts, MCP schemas, token revocation, and degraded-state
visibility. Human/model interview scoring remains a reproducible submission
run, not a fabricated repository fixture result.

## Architecture-awareness verification

The automated architecture corpus covers both declaration dialects, repeated
H2 headings, conflicts, missing-card gaps, path/symlink/corpus bounds,
transactional activation and rejection, idempotency, health drift, alias
resolution, packet bounds, and exact evidence lookup.

The pinned-handoff test activates revision one, publishes its ArchitectureBrief,
activates revision two, and proves that alias-based load still reports revision
one, old evidence remains resolvable, a new task pack reports revision two, and
the graph retains the historical source and Codex activation path.

The optional PostgreSQL behavioral test performs migration 5 on a real server,
transitions active to historical, resolves old bytes, re-instantiates the
adapter, and retrieves the new brief. It passed before and after a clean server
restart. This proves storage behavioral parity; it does not claim a deployed
Cloud SQL or Cloud Run smoke test.
