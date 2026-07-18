from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from array import array
from dataclasses import dataclass
from typing import Iterable

try:  # Optional acceleration; the product remains fully functional without it.
    import numpy as np
except ImportError:  # pragma: no cover - exercised by the no-NumPy subprocess test
    np = None  # type: ignore[assignment]

from .config import Settings
from .db import Database
from .models import EmbeddingStatus, MemoryRecord, SyncResponse, utc_now

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+-]*", re.I)
SEMANTIC_ALIASES = {
    "semantic": "dense",
    "offline": "failure",
    "inspectable": "auditable",
    "identifiers": "ids",
    "typing": "typed",
    "speaking": "voice",
    "handset": "mobile",
    "neural": "npu",
    "approve": "confirm",
    "permission": "consent",
    "fake": "simulated",
}


def canonical_surface(memory: MemoryRecord) -> str:
    """Stable surface; intentionally excludes IDs and arbitrary metadata."""
    return (
        f"type: {memory.entity_type}\nproject: {memory.project}\n"
        f"kind: {memory.kind}\nstatus: {memory.status}\n"
        f"tags: {', '.join(sorted(memory.tags))}\ntitle: {memory.title}\n"
        f"content: {memory.content}\nreason: {memory.reason}"
    )


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class EmbeddingProvider(ABC):
    name: str
    model: str
    dimensions: int

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class HashEmbeddingProvider(EmbeddingProvider):
    name = "hash"

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions
        self.model = f"hash-{dimensions}"

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for raw_token in TOKEN_RE.findall(text.lower()):
            token = SEMANTIC_ALIASES.get(raw_token, raw_token)
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            vector[index] += 1.0 if digest[4] & 1 else -1.0
        return normalize_vector(vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, dimensions: int = 256):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 64):
            response = self.client.embeddings.create(
                model=self.model, dimensions=self.dimensions,
                encoding_format="float", input=texts[start : start + 64],
            )
            vectors.extend(x.embedding for x in sorted(response.data, key=lambda x: x.index))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.model, dimensions=self.dimensions,
            encoding_format="float", input=text,
        )
        return response.data[0].embedding


def create_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        return OpenAIEmbeddingProvider(
            settings.openai_api_key, settings.embedding_model,
            settings.embedding_dimensions,
        )
    return HashEmbeddingProvider(settings.embedding_dimensions)


def vector_blob(vector: Iterable[float]) -> bytes:
    return array("f", vector).tobytes()


def vector_from_blob(blob: bytes) -> list[float]:
    values = array("f")
    values.frombytes(blob)
    return list(values)


def normalize_vector(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values] if norm else values


def cosine_scores(vectors: list[list[float]], query: list[float]) -> list[float]:
    """Cosine over normalized vectors, with NumPy as a transparent accelerator."""
    normalized = normalize_vector(query)
    if np is not None and vectors:
        matrix = np.asarray(vectors, dtype=np.float32)
        return list(map(float, matrix @ np.asarray(normalized, dtype=np.float32)))
    return [sum(left * right for left, right in zip(vector, normalized, strict=True))
            for vector in vectors]


@dataclass
class DenseIndex:
    ids: list[str]
    vectors: list[list[float]]


class EmbeddingStore:
    def __init__(self, db: Database, provider: EmbeddingProvider):
        self.db, self.provider = db, provider
        self.degraded = False
        self.index = DenseIndex([], [])
        self.reload()

    def reload(self) -> None:
        ids, vectors = [], []
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT e.memory_id,e.vector FROM embeddings e
                JOIN memories m ON m.id=e.memory_id
                WHERE e.provider=? AND e.model=? AND e.dimensions=?
                AND NOT(m.entity_type='fact' AND m.status!='active')
                ORDER BY e.memory_id""",
                (self.provider.name, self.provider.model, self.provider.dimensions),
            ).fetchall()
        for row in rows:
            vector = vector_from_blob(row["vector"])
            if len(vector) != self.provider.dimensions:
                self.degraded = True
                continue
            vectors.append(normalize_vector(vector))
            ids.append(row["memory_id"])
        self.index = DenseIndex(ids, vectors)

    def status(self) -> EmbeddingStatus:
        with self.db.connect() as conn:
            eligible = int(conn.execute(
                "SELECT COUNT(*) FROM memories WHERE NOT(entity_type='fact' AND status!='active')"
            ).fetchone()[0])
            indexed = int(conn.execute(
                """SELECT COUNT(*) FROM embeddings e JOIN memories m ON m.id=e.memory_id
                WHERE e.provider=? AND e.model=? AND e.dimensions=?
                AND NOT(m.entity_type='fact' AND m.status!='active')""",
                (self.provider.name, self.provider.model, self.provider.dimensions),
            ).fetchone()[0])
        return EmbeddingStatus(
            provider=self.provider.name, model=self.provider.model,
            dimensions=self.provider.dimensions, indexed=indexed, eligible=eligible,
            pending=max(eligible-indexed, 0), coverage=indexed/eligible if eligible else 1,
            degraded=self.degraded,
        )

    def sync(self) -> SyncResponse:
        memories = self.db.list_memories()
        wanted = {
            m.id: (content_hash(canonical_surface(m)), canonical_surface(m))
            for m in memories
        }
        with self.db.connect() as conn:
            cached = {
                row["memory_id"]: row["content_hash"]
                for row in conn.execute(
                    "SELECT memory_id,content_hash FROM embeddings "
                    "WHERE provider=? AND model=? AND dimensions=?",
                    (self.provider.name, self.provider.model, self.provider.dimensions),
                )
            }
        changed = [key for key, value in wanted.items() if cached.get(key) != value[0]]
        stale = set(cached) - set(wanted)
        indexed = failed = 0
        try:
            vectors = self.provider.embed_documents([wanted[key][1] for key in changed])
            if len(vectors) != len(changed):
                raise ValueError("wrong embedding count")
            with self.db.transaction() as conn:
                for key, vector in zip(changed, vectors, strict=True):
                    if len(vector) != self.provider.dimensions:
                        raise ValueError("wrong embedding dimensions")
                    conn.execute(
                        """INSERT INTO embeddings(memory_id,content_hash,provider,model,
                        dimensions,vector,updated_at) VALUES(?,?,?,?,?,?,?)
                        ON CONFLICT(memory_id) DO UPDATE SET
                        content_hash=excluded.content_hash,provider=excluded.provider,
                        model=excluded.model,dimensions=excluded.dimensions,
                        vector=excluded.vector,updated_at=excluded.updated_at""",
                        (key, wanted[key][0], self.provider.name, self.provider.model,
                         self.provider.dimensions, vector_blob(vector), utc_now()),
                    )
                    indexed += 1
                for key in stale:
                    conn.execute("DELETE FROM embeddings WHERE memory_id=?", (key,))
        except Exception:
            failed = len(changed)
            self.degraded = True
        self.reload()
        return SyncResponse(
            indexed=indexed, deleted=len(stale), unchanged=len(wanted)-len(changed),
            failed=failed, status=self.status(),
        )

    def query(self, text: str) -> tuple[dict[str, float], bool]:
        if not self.index.ids:
            return {}, self.degraded
        try:
            query = self.provider.embed_query(text)
            if len(query) != self.provider.dimensions:
                raise ValueError("wrong query dimensions")
            scores = cosine_scores(self.index.vectors, query)
            return dict(zip(self.index.ids, map(float, scores), strict=True)), False
        except Exception:
            self.degraded = True
            return {}, True
