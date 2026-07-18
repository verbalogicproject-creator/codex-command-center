from __future__ import annotations

import math
import re
import time
from collections import Counter

from .db import Database
from .embeddings import EmbeddingStore
from .models import RecallHit, RecallRequest, RecallResponse, RetrievalTrace

WORD_RE = re.compile(r"[a-z0-9][a-z0-9_+-]*", re.I)


def words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


class Retriever:
    def __init__(self, db: Database, embeddings: EmbeddingStore):
        self.db, self.embeddings = db, embeddings

    def recall(self, request: RecallRequest) -> RecallResponse:
        started = time.perf_counter()
        memories = self.db.list_memories(request.project, request.kinds)
        query = words(request.query)
        document_frequency: Counter[str] = Counter()
        documents: dict[str, list[str]] = {}
        for memory in memories:
            documents[memory.id] = words(" ".join([
                memory.project, memory.kind, memory.status, memory.title,
                memory.content, memory.reason, *memory.tags,
            ]))
            document_frequency.update(set(documents[memory.id]))
        dense, degraded = self.embeddings.query(request.query)
        hits = []
        for memory in memories:
            counts = Counter(documents[memory.id])
            lexical = sum(
                math.log(1 + max(len(memories), 1) / (1 + document_frequency[token]))
                * (1 + math.log(counts[token]))
                for token in query if counts[token]
            ) / max(len(query), 1)
            dense_score = max(dense.get(memory.id, 0), 0)
            structural = 0.3 if memory.project.lower() in request.query.lower() else 0
            if memory.kind in {"decision", "architecture"} and any(
                token in query for token in ("decision", "architecture", "build", "power")
            ):
                structural += 0.2
            score = lexical * .48 + dense_score * .42 + structural
            if score > 0:
                provenance = [
                    name for name, value in (
                        ("lexical", lexical), ("dense", dense_score), ("structural", structural)
                    ) if value > 0
                ]
                hits.append(RecallHit(
                    memory=memory, score=round(score, 6),
                    lexical_score=round(lexical, 6), dense_score=round(dense_score, 6),
                    structural_score=round(structural, 6), provenance=provenance,
                ))
        hits.sort(key=lambda item: (item.score, item.memory.happened_at), reverse=True)
        return RecallResponse(
            hits=hits[:request.limit],
            trace=RetrievalTrace(
                query_ms=round((time.perf_counter()-started)*1000, 2),
                candidates=len(memories), embedding_provider=self.embeddings.provider.name,
                query_embedding_calls=1 if self.embeddings.index.ids else 0,
                degraded=degraded, signals=["bm25-like", "dense-cosine", "project", "intent"],
            ),
        )
