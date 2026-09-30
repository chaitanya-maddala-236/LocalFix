from __future__ import annotations

import importlib.util
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np

from ..database import connect
from ..schemas import Evidence


class LocalEmbeddingIndex:
    """FastEmbed index with an explicit local-only runtime and SQLite vectors."""

    def __init__(self, project_root: Path, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.project_root = project_root.resolve()
        self.model_name = model_name
        self.cache_dir = self.project_root / "models" / "embeddings"
        self.model: Any = None
        self.state = "NOT_INSTALLED"
        self.error: str | None = None
        self.load_ms: float | None = None
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        if self.state == "READY" and self.model is not None:
            return self.health()
        if importlib.util.find_spec("fastembed") is None:
            self.state = "NOT_INSTALLED"
            return self.health()
        if not any(self.cache_dir.rglob("*.onnx")):
            self.state = "MODEL_REQUIRED"
            return self.health()
        try:
            from fastembed import TextEmbedding

            started = __import__("time").perf_counter()
            with self._lock:
                self.model = TextEmbedding(
                    model_name=self.model_name, cache_dir=str(self.cache_dir),
                    local_files_only=True, providers=["CPUExecutionProvider"], threads=max(1, min(4, os.cpu_count() or 1)),
                )
                # Force model/session initialization now. This API path never downloads weights.
                next(iter(self.model.embed(["LocalFix offline model warmup"])))
            self.load_ms = round((__import__("time").perf_counter() - started) * 1000, 3)
            self.state = "READY"
            self.error = None
        except Exception as error:
            self.model = None
            self.state = "ERROR"
            self.error = f"{type(error).__name__}: {error}"
        return self.health()

    def embed(self, texts: list[str], *, query: bool = False) -> list[np.ndarray]:
        if self.state != "READY" or self.model is None:
            raise RuntimeError("Local semantic embeddings are not ready")
        if not texts:
            return []
        with self._lock:
            embed_fn = getattr(self.model, "query_embed", None) if query else None
            stream = embed_fn(texts) if embed_fn else self.model.embed(texts)
            return [np.asarray(vector, dtype=np.float32) for vector in stream]

    def embed_unindexed(self, batch_size: int = 64) -> int:
        if self.state != "READY":
            return 0
        updated = 0
        with connect() as connection:
            rows = connection.execute(
                "SELECT chunk_id,text FROM manual_chunks WHERE embedding IS NULL OR embedding_model<>?",
                (self.model_name,),
            ).fetchall()
        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]
            vectors = self.embed([row["text"] for row in batch])
            with connect() as connection:
                connection.executemany(
                    "UPDATE manual_chunks SET embedding=?,embedding_model=? WHERE chunk_id=?",
                    [(vector.astype("<f4", copy=False).tobytes(), self.model_name, row["chunk_id"])
                     for row, vector in zip(batch, vectors)],
                )
            updated += len(batch)
        return updated

    def embed_document(self, document_id: str, batch_size: int = 64) -> int:
        if self.state != "READY":
            return 0
        with connect() as connection:
            rows = connection.execute(
                "SELECT chunk_id,text FROM manual_chunks WHERE document_id=? AND (embedding IS NULL OR embedding_model<>?)",
                (document_id, self.model_name),
            ).fetchall()
        updated = 0
        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]
            vectors = self.embed([row["text"] for row in batch])
            with connect() as connection:
                connection.executemany(
                    "UPDATE manual_chunks SET embedding=?,embedding_model=? WHERE chunk_id=?",
                    [(vector.astype("<f4", copy=False).tobytes(), self.model_name, row["chunk_id"])
                     for row, vector in zip(batch, vectors)],
                )
            updated += len(batch)
        return updated

    def retrieve(self, query: str, equipment_model: str | None, top_k: int) -> list[Evidence]:
        if self.state != "READY":
            return []
        query_vector = self.embed([query], query=True)[0]
        filter_sql = "AND (c.equipment_model=? OR c.equipment_model IS NULL)" if equipment_model else ""
        params: tuple[Any, ...] = (self.model_name, equipment_model) if equipment_model else (self.model_name,)
        with connect() as connection:
            rows = connection.execute(
                """SELECT c.chunk_id,c.document_id,d.document_name,c.page,c.section,c.equipment_model,
                          c.text,c.source_hash,c.embedding
                   FROM manual_chunks c JOIN documents d ON d.document_id=c.document_id
                   WHERE c.embedding_model=? AND c.embedding IS NOT NULL """ + filter_sql,
                params,
            ).fetchall()
        candidates: list[tuple[float, Evidence]] = []
        query_norm = float(np.linalg.norm(query_vector)) or 1.0
        for row in rows:
            vector = np.frombuffer(row["embedding"], dtype="<f4")
            if vector.shape != query_vector.shape:
                continue
            denom = query_norm * (float(np.linalg.norm(vector)) or 1.0)
            score = float(np.dot(query_vector, vector) / denom)
            item = Evidence(
                id=row["chunk_id"], document_id=row["document_id"], document_name=row["document_name"],
                page=row["page"], section=row["section"], equipment_model=row["equipment_model"],
                text=row["text"], retrieval_score=score, source_hash=row["source_hash"],
            )
            candidates.append((score, item))
        candidates.sort(key=lambda candidate: candidate[0], reverse=True)
        return [item for _, item in candidates[:top_k]]

    def health(self) -> dict[str, Any]:
        return {
            "stage": "embedding", "state": self.state, "model": self.model_name if self.state == "READY" else None,
            "path_configured": True, "file_present": any(self.cache_dir.rglob("*.onnx")),
            "backend": "ONNX Runtime · CPU" if self.state == "READY" else None,
            "active_providers": ["CPUExecutionProvider"] if self.state == "READY" else [],
            "available_providers": [], "precision": "FP32", "load_ms": self.load_ms,
            "error": self.error,
        }


def hybrid_retrieve(query: str, equipment_model: str | None, top_k: int,
                    embedding_index: LocalEmbeddingIndex, lexical_retrieve: Any) -> list[Evidence]:
    lexical = lexical_retrieve(query, equipment_model, max(20, top_k * 4))
    semantic = embedding_index.retrieve(query, equipment_model, max(20, top_k * 4))
    if not semantic:
        return lexical[:top_k]

    scores: dict[str, float] = {}
    by_id: dict[str, Evidence] = {}
    rank_constant = 60.0
    for results, weight in ((lexical, 0.75), (semantic, 0.25)):
        for rank, item in enumerate(results, start=1):
            by_id[item.id] = item
            scores[item.id] = scores.get(item.id, 0.0) + weight / (rank_constant + rank)
    max_score = max(scores.values()) if scores else 1.0
    ranked = sorted(scores, key=scores.get, reverse=True)[:top_k]
    return [by_id[evidence_id].model_copy(update={"retrieval_score": round(scores[evidence_id] / max_score, 6)})
            for evidence_id in ranked]
