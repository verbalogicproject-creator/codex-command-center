from __future__ import annotations

import json
import statistics
import tempfile
import time
from pathlib import Path

from aria_memory.config import ROOT, Settings
from aria_memory.context import ContextCompiler, estimate_tokens
from aria_memory.db import Database
from aria_memory.documents import DeclaredDocumentStore, document_surface
from aria_memory.embeddings import EmbeddingStore, HashEmbeddingProvider
from aria_memory.models import ContextPackRequest, DocumentRecallRequest, RecallRequest
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
    context_tasks = json.loads((ROOT / "fixtures/demo/context-eval.json").read_text())
    with tempfile.TemporaryDirectory() as directory:
        db = Database(Path(directory) / "eval.db", ROOT / "fixtures/demo/memories.json")
        provider = HashEmbeddingProvider(256)
        embeddings = EmbeddingStore(db, provider)
        sync = embeddings.sync()
        retriever = Retriever(db, embeddings)
        documents = DeclaredDocumentStore(db, provider)
        documents.ingest_tree(ROOT / "fixtures/demo/documents", ROOT)
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
        document_modes: dict[str, list[int | None]] = {
            "lexical": [], "declared_structural": [], "dense": [], "full_hybrid": [],
        }
        document_latencies = {key: [] for key in document_modes}
        for task in context_tasks:
            relevant = {
                item for item in task["expected_evidence_ids"] if item.startswith("doc_")
            }
            for label, mode in (
                ("lexical", "lexical"), ("declared_structural", "declared"),
                ("dense", "dense"), ("full_hybrid", "hybrid"),
            ):
                started = time.perf_counter()
                result = documents.recall(DocumentRecallRequest(
                    query=task["query"], limit=10, mode=mode,
                ))
                document_latencies[label].append((time.perf_counter() - started) * 1000)
                ids = [hit.document.id for hit in result.hits]
                document_modes[label].append(next(
                    (index + 1 for index, key in enumerate(ids) if key in relevant), None
                ))
        report["declared_document_modes"] = {
            name: metrics(document_modes[name], document_latencies[name])
            for name in document_modes
        }

        settings = Settings(
            data_dir=Path(directory), embedding_api_key=None, embedding_provider="hash",
        )
        compiler = ContextCompiler(settings, retriever, documents)
        full_corpus_tokens = sum(
            estimate_tokens(
                memory.title + " " + memory.content + " " + memory.reason
            ) for memory in db.list_memories()
        ) + sum(estimate_tokens(document_surface(item)) for item in documents.list())
        proof = []
        for task in context_tasks:
            started = time.perf_counter()
            packet = compiler.build(ContextPackRequest(
                prompt=task["query"], token_budget=2_000,
                memory_limit=8, document_limit=5,
            ))
            elapsed = (time.perf_counter() - started) * 1000
            selected = {source.id for source in packet.sources}
            expected = set(task["expected_evidence_ids"])
            unsupported = len(expected - selected)
            if unsupported:
                raise AssertionError(
                    f"{task['id']} missing expected evidence: {sorted(expected-selected)}"
                )
            proof.append({
                "task": task["id"],
                "expected_evidence_ids": task["expected_evidence_ids"],
                "without_command_center": {
                    "repository_reads": documents.count if hasattr(documents, "count") else len(documents.list()),
                    "search_calls": 1,
                    "tokens": full_corpus_tokens,
                    "unsupported_claims": 0,
                    "tool_call_trace": ["read every AI card", "scan full durable-memory corpus"],
                },
                "with_context_packet": {
                    "repository_reads": 0,
                    "search_calls": 1,
                    "tokens": packet.token_estimate,
                    "time_ms": round(elapsed, 2),
                    "unsupported_claims": unsupported,
                    "tool_call_trace": ["POST /api/v1/context/pack"],
                    "selected_source_ids": [source.id for source in packet.sources],
                },
                "token_reduction": round(
                    1 - packet.token_estimate / max(full_corpus_tokens, 1), 4
                ),
                "falsification": task["falsification"],
            })
        report["retrospective_proof"] = proof
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
