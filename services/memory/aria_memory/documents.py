from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from declared_core import classify_intent, rrf_fuse, sanitize_query, structural_paths
from frontmatter_rag import COMMAND_CENTER_AI_CARD, first_h1, parse_frontmatter
from frontmatter_rag.parse import as_list

from .db import Database
from .embeddings import (
    EmbeddingProvider,
    content_hash,
    cosine_scores,
    normalize_vector,
    vector_blob,
    vector_from_blob,
)
from .models import (
    DeclaredDimensions,
    DocumentHit,
    DocumentRecallRequest,
    DocumentRecallResponse,
    DocumentRecord,
    RetrievalTrace,
    utc_now,
)

SCHEMA = COMMAND_CENTER_AI_CARD
DIMENSION_NAMES = (
    "privacy", "local_first", "mobile_suitability", "inspectability",
    "implementation_maturity", "evidence_strength", "operational_risk",
    "decision_relevance",
)
QUERY_DIMENSION_CUES = {
    "privacy": {"privacy", "private", "personal", "sensitive", "consent"},
    "local_first": {"local", "offline", "device", "sqlite", "local-first"},
    "mobile_suitability": {"mobile", "phone", "device", "android", "handset"},
    "inspectability": {"inspect", "evidence", "audit", "trace", "receipt", "provenance"},
    "implementation_maturity": {"implemented", "shipped", "ready", "mature", "working"},
    "evidence_strength": {"evidence", "verified", "test", "proof", "source"},
    "operational_risk": {"risk", "failure", "unsafe", "outage", "guard"},
    "decision_relevance": {"decision", "choose", "recommend", "architecture", "tradeoff"},
}


def _safe_list(value: Any) -> list[str]:
    return as_list(value)


def document_surface(document: DocumentRecord) -> str:
    return "\n".join([
        f"repository: {document.repository}",
        f"kind: {document.kind}",
        f"status: {document.status}",
        f"title: {document.title}",
        f"provides: {' '.join(document.provides)}",
        f"interfaces: {' '.join(document.public_interfaces)}",
        f"safe edit points: {' '.join(document.safe_edit_points)}",
        f"risk areas: {' '.join(document.risk_areas)}",
        f"entities: {' '.join(document.graph_rag_entities)}",
        f"dependencies: {' '.join(document.depends_on)}",
        f"main files: {' '.join(document.main_files)}",
        f"body: {document.body}",
    ])


def _document_id(source_uri: str, declared: str | None) -> str:
    if declared and declared.strip():
        return declared.strip()
    return "doc_" + hashlib.sha256(source_uri.encode()).hexdigest()[:16]


class DeclaredDocumentStore:
    """Frontmatter ingestion, declared retrieval, and persistent dense recall."""

    def __init__(self, db: Database, provider: EmbeddingProvider):
        self.db = db
        self.provider = provider
        self.degraded = False
        self.ids: list[str] = []
        self.vectors: list[list[float]] = []
        self._install_fts()
        self.reload_embeddings()

    def _install_fts(self) -> None:
        if self.db.dialect != "sqlite":
            return
        fields = ("title", "body", "provides_json", "public_interfaces_json",
                  "safe_edit_points_json", "risk_areas_json")
        columns = ", ".join(fields)
        new_values = ", ".join(f"coalesce(new.{field}, '')" for field in fields)
        old_values = ", ".join(f"coalesce(old.{field}, '')" for field in fields)
        with self.db.transaction() as conn:
            conn.execute(
                f"""CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                {columns}, content=documents, content_rowid=rowid,
                tokenize='porter unicode61')"""
            )
            conn.execute(
                f"""CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid,{columns}) VALUES(new.rowid,{new_values}); END"""
            )
            conn.execute(
                f"""CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts,rowid,{columns})
                VALUES('delete',old.rowid,{old_values}); END"""
            )
            conn.execute(
                f"""CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts,rowid,{columns})
                VALUES('delete',old.rowid,{old_values});
                INSERT INTO documents_fts(rowid,{columns}) VALUES(new.rowid,{new_values}); END"""
            )
            conn.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")

    def ingest_tree(self, root: Path, repository_root: Path) -> dict[str, int]:
        scanned = ingested = skipped = 0
        wanted: set[str] = set()
        if not root.exists():
            return {"scanned": 0, "ingested": 0, "skipped": 0, "deleted": 0}
        for path in sorted(root.rglob("*.md")):
            scanned += 1
            try:
                source_uri = path.resolve().relative_to(repository_root.resolve()).as_posix()
            except ValueError:
                skipped += 1
                continue
            result = self.ingest_text(path.read_text(encoding="utf-8"), source_uri)
            if result:
                wanted.add(result)
                ingested += 1
            else:
                skipped += 1
        prefix = root.resolve().relative_to(repository_root.resolve()).as_posix().rstrip("/") + "/"
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM documents WHERE source_uri LIKE ?", (prefix + "%",)
            ).fetchall()
            stale = [row["id"] for row in existing if row["id"] not in wanted]
            for document_id in stale:
                conn.execute("DELETE FROM documents WHERE id=?", (document_id,))
        self.sync_embeddings()
        return {
            "scanned": scanned, "ingested": ingested, "skipped": skipped,
            "deleted": len(stale),
        }

    def ingest_text(self, text: str, source_uri: str) -> str | None:
        if source_uri.startswith("/") or ".." in Path(source_uri).parts:
            raise ValueError("document source_uri must be repository-relative")
        frontmatter, body = parse_frontmatter(text)
        if frontmatter is None:
            return None
        document_id = _document_id(source_uri, frontmatter.get(SCHEMA.id_key))
        raw_dimensions = frontmatter.get("dimensions") or {}
        if not isinstance(raw_dimensions, dict):
            raw_dimensions = {}
        dimensions = DeclaredDimensions(**{
            key.replace("-", "_"): value for key, value in raw_dimensions.items()
            if key.replace("-", "_") in DIMENSION_NAMES
        })
        document = DocumentRecord(
            id=document_id,
            source_uri=source_uri,
            repository=str(frontmatter.get("repository") or frontmatter.get("project") or ""),
            title=str(frontmatter.get("title") or first_h1(body) or Path(source_uri).stem),
            body=body.strip(),
            provides=_safe_list(frontmatter.get("provides")),
            public_interfaces=_safe_list(frontmatter.get("public_interfaces")),
            safe_edit_points=_safe_list(frontmatter.get("safe_edit_points")),
            risk_areas=_safe_list(frontmatter.get("risk_areas")),
            graph_rag_entities=_safe_list(frontmatter.get("graph_rag_entities")),
            depends_on=_safe_list(frontmatter.get("depends_on")),
            main_files=_safe_list(frontmatter.get("main_files")),
            kind=str(frontmatter.get("kind") or "ai-card"),
            status=str(frontmatter.get("status") or "active"),
            owner_area=str(frontmatter.get("owner_area") or ""),
            audience=str(frontmatter.get("audience") or ""),
            last_verified=(
                str(frontmatter.get("last_verified"))
                if frontmatter.get("last_verified") is not None else None
            ),
            dimensions=dimensions,
        )
        if not document.repository:
            return None
        surface_hash = content_hash(document_surface(document))
        values = (
            document.id, document.source_uri, document.repository, document.title,
            document.body, *(
                json.dumps(getattr(document, field))
                for field in (
                    "provides", "public_interfaces", "safe_edit_points", "risk_areas",
                    "graph_rag_entities", "depends_on", "main_files",
                )
            ),
            document.kind, document.status, document.owner_area, document.audience,
            document.last_verified, document.dimensions.model_dump_json(),
            surface_hash, utc_now(),
        )
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_uri) DO UPDATE SET
                repository=excluded.repository,title=excluded.title,body=excluded.body,
                provides_json=excluded.provides_json,
                public_interfaces_json=excluded.public_interfaces_json,
                safe_edit_points_json=excluded.safe_edit_points_json,
                risk_areas_json=excluded.risk_areas_json,
                graph_rag_entities_json=excluded.graph_rag_entities_json,
                depends_on_json=excluded.depends_on_json,main_files_json=excluded.main_files_json,
                kind=excluded.kind,status=excluded.status,owner_area=excluded.owner_area,
                audience=excluded.audience,last_verified=excluded.last_verified,
                dimensions_json=excluded.dimensions_json,content_hash=excluded.content_hash,
                updated_at=excluded.updated_at""",
                values,
            )
        return document_id

    @staticmethod
    def _from_row(row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            id=row["id"], source_uri=row["source_uri"], repository=row["repository"],
            title=row["title"], body=row["body"],
            **{
                field: json.loads(row[f"{field}_json"])
                for field in (
                    "provides", "public_interfaces", "safe_edit_points", "risk_areas",
                    "graph_rag_entities", "depends_on", "main_files",
                )
            },
            kind=row["kind"], status=row["status"], owner_area=row["owner_area"],
            audience=row["audience"], last_verified=row["last_verified"],
            dimensions=DeclaredDimensions(**json.loads(row["dimensions_json"])),
        )

    def get(self, document_id: str) -> DocumentRecord | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        return self._from_row(row) if row else None

    def list(self, repository: str | None = None) -> list[DocumentRecord]:
        sql = "SELECT * FROM documents WHERE status!='inactive'"
        args: tuple[str, ...] = ()
        if repository:
            sql += " AND lower(repository)=lower(?)"
            args = (repository,)
        with self.db.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [self._from_row(row) for row in rows]

    def reload_embeddings(self) -> None:
        ids: list[str] = []
        vectors: list[list[float]] = []
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT document_id,vector FROM document_embeddings
                WHERE provider=? AND model=? AND dimensions=? ORDER BY document_id""",
                (self.provider.name, self.provider.model, self.provider.dimensions),
            ).fetchall()
        for row in rows:
            vector = vector_from_blob(row["vector"])
            if len(vector) != self.provider.dimensions:
                self.degraded = True
                continue
            ids.append(row["document_id"])
            vectors.append(normalize_vector(vector))
        self.ids, self.vectors = ids, vectors

    def sync_embeddings(self) -> dict[str, int]:
        documents = self.list()
        wanted = {
            document.id: (content_hash(document_surface(document)), document_surface(document))
            for document in documents
        }
        with self.db.connect() as conn:
            cached = {
                row["document_id"]: row["content_hash"]
                for row in conn.execute(
                    """SELECT document_id,content_hash FROM document_embeddings
                    WHERE provider=? AND model=? AND dimensions=?""",
                    (self.provider.name, self.provider.model, self.provider.dimensions),
                )
            }
        changed = [key for key, value in wanted.items() if cached.get(key) != value[0]]
        stale = set(cached) - set(wanted)
        indexed = failed = 0
        try:
            vectors = self.provider.embed_documents([wanted[key][1] for key in changed])
            with self.db.transaction() as conn:
                for key, vector in zip(changed, vectors, strict=True):
                    if len(vector) != self.provider.dimensions:
                        raise ValueError("wrong document embedding dimensions")
                    conn.execute(
                        """INSERT INTO document_embeddings VALUES(?,?,?,?,?,?,?)
                        ON CONFLICT(document_id) DO UPDATE SET
                        content_hash=excluded.content_hash,provider=excluded.provider,
                        model=excluded.model,dimensions=excluded.dimensions,
                        vector=excluded.vector,updated_at=excluded.updated_at""",
                        (key, wanted[key][0], self.provider.name, self.provider.model,
                         self.provider.dimensions, vector_blob(vector), utc_now()),
                    )
                    indexed += 1
                for key in stale:
                    conn.execute("DELETE FROM document_embeddings WHERE document_id=?", (key,))
        except Exception:
            self.degraded = True
            failed = len(changed)
        self.reload_embeddings()
        return {"indexed": indexed, "deleted": len(stale), "failed": failed}

    def _dense(self, query: str) -> tuple[dict[str, float], bool]:
        if not self.ids:
            return {}, self.degraded
        try:
            vector = self.provider.embed_query(query)
            if len(vector) != self.provider.dimensions:
                raise ValueError("wrong document query dimensions")
            return dict(zip(self.ids, cosine_scores(self.vectors, vector), strict=True)), False
        except Exception:
            self.degraded = True
            return {}, True

    def recall(self, request: DocumentRecallRequest) -> DocumentRecallResponse:
        started = time.perf_counter()
        documents = self.list(request.repository)
        by_id = {document.id: document for document in documents}
        lexical_rows: list[dict[str, Any]] = []
        fts_query = sanitize_query(request.query)
        if fts_query and self.db.dialect == "sqlite":
            sql = """SELECT d.id,bm25(documents_fts) rank FROM documents_fts
            JOIN documents d ON d.rowid=documents_fts.rowid
            WHERE documents_fts MATCH ? AND d.status!='inactive'"""
            args: list[Any] = [fts_query]
            if request.repository:
                sql += " AND lower(d.repository)=lower(?)"
                args.append(request.repository)
            sql += " ORDER BY rank LIMIT 25"
            with self.db.connect() as conn:
                lexical_rows = [
                    {"table": "documents", "id": row["id"],
                     "lexical_score": 1 / (1 + abs(float(row["rank"])))}
                    for row in conn.execute(sql, args).fetchall()
                ]
        elif fts_query:
            terms = set(re.findall(r"[a-z0-9]+", request.query.casefold()))
            scored = []
            for document in documents:
                surface = document_surface(document).casefold()
                matched = sum(surface.count(term) for term in terms)
                if matched:
                    scored.append((document.id, matched / max(len(terms), 1)))
            scored.sort(key=lambda item: item[1], reverse=True)
            lexical_rows = [
                {"table": "documents", "id": document_id,
                 "lexical_score": score}
                for document_id, score in scored[:25]
            ]

        anchors = [by_id[row["id"]].model_dump() for row in lexical_rows if row["id"] in by_id]
        structural_rows: list[dict[str, Any]] = []
        for document in documents:
            paths: list[str] = []
            for anchor in anchors[:8]:
                if anchor["id"] == document.id:
                    continue
                paths.extend(structural_paths(
                    anchor, document.model_dump(),
                    cluster_fields=SCHEMA.clusters, edge_fields=SCHEMA.edges,
                ))
            if paths:
                structural_rows.append({
                    "table": "documents", "id": document.id,
                    "structural_score": min(1.0, len(paths) * .2),
                    "structural_paths": list(dict.fromkeys(paths))[:8],
                })
        structural_rows.sort(key=lambda item: item["structural_score"], reverse=True)

        dense_scores: dict[str, float] = {}
        dense_degraded = False
        if request.mode in {"dense", "hybrid"}:
            dense_scores, dense_degraded = self._dense(request.query)
        dense_rows = [
            {"table": "documents", "id": key, "dense_score": max(score, 0)}
            for key, score in sorted(dense_scores.items(), key=lambda item: item[1], reverse=True)
            if key in by_id and score > 0
        ]

        declared_rows = []
        for document in documents:
            contributions = self._dimension_contributions(document, request.query)
            declared_rows.append({
                "table": "documents", "id": document.id,
                "declared_score": sum(contributions.values()) / len(contributions),
                "dimension_contributions": contributions,
            })
        declared_rows.sort(key=lambda item: item["declared_score"], reverse=True)

        intent = classify_intent(request.query)
        lexical_label = "bm25" if self.db.dialect == "sqlite" else "lexical"
        if request.mode == "lexical":
            fused = rrf_fuse([lexical_rows], weights=[1], labels=[lexical_label])
        elif request.mode == "declared":
            fused = rrf_fuse(
                [lexical_rows, structural_rows, declared_rows],
                weights=intent.weights[:3],
                labels=[lexical_label, "structural", "declared"],
            )
        elif request.mode == "dense":
            fused = rrf_fuse([dense_rows], weights=[1], labels=["dense"])
        else:
            fused = rrf_fuse(
                [lexical_rows, structural_rows, declared_rows, dense_rows],
                weights=intent.weights,
                labels=[lexical_label, "structural", "declared", "dense"],
            )
        fields: dict[str, dict[str, Any]] = {}
        for row in lexical_rows + structural_rows + declared_rows + dense_rows:
            fields.setdefault(row["id"], {}).update(row)
        hits = []
        for fused_hit in fused[:request.limit]:
            document_id = fused_hit["id"]
            values = fields.get(document_id, {})
            hits.append(DocumentHit(
                document=by_id[document_id],
                score=round(float(fused_hit["rrf_score"]), 6),
                lexical_score=round(float(values.get("lexical_score", 0)), 6),
                dense_score=round(float(values.get("dense_score", 0)), 6),
                structural_score=round(float(values.get("structural_score", 0)), 6),
                declared_score=round(float(values.get("declared_score", 0)), 6),
                dimension_contributions=values.get("dimension_contributions", {}),
                structural_paths=values.get("structural_paths", []),
                provenance=fused_hit["rrf_sources"],
            ))
        return DocumentRecallResponse(
            hits=hits,
            trace=RetrievalTrace(
                query_ms=round((time.perf_counter() - started) * 1000, 2),
                candidates=len(documents), embedding_provider=self.provider.name,
                query_embedding_calls=1 if self.ids and request.mode in {"dense", "hybrid"} else 0,
                degraded=dense_degraded,
                signals=[
                    ("fts5-bm25" if self.db.dialect == "sqlite"
                     else "postgres-portable-lexical"),
                    "declared-structure", "declared-dimensions",
                         "dense-cosine", f"intent:{intent.intent}", f"mode:{request.mode}"],
            ),
        )

    @staticmethod
    def _dimension_contributions(
        document: DocumentRecord, query: str,
    ) -> dict[str, float]:
        tokens = {token.strip(".,?!:;()[]").lower() for token in query.split()}
        raw = document.dimensions.model_dump(exclude={"schema_version"})
        contributions: dict[str, float] = {}
        for name in DIMENSION_NAMES:
            value = float(raw.get(name, .5))
            relevant = bool(tokens & QUERY_DIMENSION_CUES[name])
            if name == "operational_risk":
                contribution = value if relevant else (1 - value)
            else:
                contribution = value if relevant else value * .5
            contributions[name] = round(contribution, 4)
        return contributions
