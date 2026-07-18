from __future__ import annotations

import json
import statistics
import tempfile
import time
from pathlib import Path

from aria_memory.config import ROOT, Settings
from aria_memory.db import Database
from aria_memory.embeddings import EmbeddingStore, HashEmbeddingProvider
from aria_memory.models import RecallRequest
from aria_memory.retrieval import Retriever


def metrics(ranks: list[int | None], latencies: list[float]) -> dict[str, float]:
    return {
        "queries": len(ranks),
        "recall_at_5": sum(rank is not None and rank <= 5 for rank in ranks) / len(ranks),
        "mrr": sum(1 / rank if rank else 0 for rank in ranks) / len(ranks),
        "p50_ms": statistics.median(latencies),
        "p95_ms": sorted(latencies)[int(len(latencies) * .95) - 1],
    }


def main() -> None:
    queries = json.loads((ROOT / "fixtures/demo/eval-queries.json").read_text())
    with tempfile.TemporaryDirectory() as directory:
        db = Database(Path(directory) / "eval.db", ROOT / "fixtures/demo/memories.json")
        embeddings = EmbeddingStore(db, HashEmbeddingProvider(256))
        sync = embeddings.sync()
        retriever = Retriever(db, embeddings)
        configurations = {"lexical": [], "hash_hybrid": []}
        latencies = {"lexical": [], "hash_hybrid": []}
        for item in queries:
            started = time.perf_counter()
            result = retriever.recall(RecallRequest(query=item["query"], limit=25))
            elapsed = (time.perf_counter() - started) * 1000
            relevant = set(item["relevant"])
            hybrid_ids = [hit.memory.id for hit in result.hits]
            lexical_ids = [
                hit.memory.id for hit in sorted(
                    result.hits, key=lambda hit: hit.lexical_score, reverse=True
                ) if hit.lexical_score > 0
            ]
            for name, ids in (("lexical", lexical_ids), ("hash_hybrid", hybrid_ids)):
                rank = next((i + 1 for i, key in enumerate(ids) if key in relevant), None)
                configurations[name].append(rank)
                latencies[name].append(elapsed)
        report = {
            name: metrics(configurations[name], latencies[name])
            for name in configurations
        }
        report["embedding_cache"] = {
            "initial_api_batches": 0,
            "initial_rows": sync.indexed,
            "ordinary_query_document_embeds": 0,
            "coverage": sync.status.coverage,
        }
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
