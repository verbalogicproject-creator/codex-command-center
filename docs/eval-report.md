# Retrieval evaluation

Run on 2026-07-18 with Python 3.14 on the supplied Android/Termux environment.
The public evaluation set contains 35 labelled exact, paraphrase, cross-project,
chronology, decision, architecture and constraint queries over 46 records.

| Configuration | Recall@5 | MRR | p50 | p95 |
|---|---:|---:|---:|---:|
| Lexical score | 97.1% | 0.910 | 2.68 ms | 3.01 ms |
| Cached hash hybrid | 100% | 0.913 | 2.68 ms | 3.01 ms |

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

