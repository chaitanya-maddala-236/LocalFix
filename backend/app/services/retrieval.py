from __future__ import annotations

import re
import sqlite3
from collections import OrderedDict
from typing import Any

from ..database import connect
from ..models.base import ModelRegistry
from ..schemas import Evidence

_query_cache: OrderedDict[tuple[str, str | None, int], list[Evidence]] = OrderedDict()


def _fts_expression(query: str) -> str:
    terms = re.findall(r"[\w-]+", query, flags=re.UNICODE)
    stop_words = {"why", "is", "this", "the", "a", "an", "what", "should", "i", "check", "for", "on", "my", "machine", "showing", "appearing", "with", "to", "and", "of", "do", "does", "explain", "mean", "tell", "me", "about", "it", "please"}
    terms = [term for term in terms if len(term) > 1 and term.casefold() not in stop_words][:10]
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"*' for term in terms)


def retrieve(query: str, equipment_model: str | None = None, top_k: int = 5) -> list[Evidence]:
    cache_key = (query.strip().casefold(), equipment_model.casefold() if equipment_model else None, top_k)
    if cache_key in _query_cache:
        _query_cache.move_to_end(cache_key)
        return list(_query_cache[cache_key])
    expression = _fts_expression(query)
    if not expression:
        return []
    params: list[Any] = [expression]
    model_filter = ""
    if equipment_model:
        model_filter = "AND (c.equipment_model = ? OR c.equipment_model IS NULL)"
        params.append(equipment_model)
    params.append(top_k)
    try:
        with connect() as connection:
            rows = connection.execute(
                """SELECT c.chunk_id, c.document_id, d.document_name, c.page, c.section,
                          c.equipment_model, c.text, c.source_hash, bm25(manual_chunks_fts) AS rank
                   FROM manual_chunks_fts f
                   JOIN manual_chunks c ON c.chunk_id = f.chunk_id
                   JOIN documents d ON d.document_id = c.document_id
                   WHERE manual_chunks_fts MATCH ? """ + model_filter +
                " ORDER BY rank ASC LIMIT ?", params
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    evidence: list[Evidence] = []
    for row in rows:
        raw_rank = float(row["rank"] or 0)
        evidence.append(Evidence(
            id=row["chunk_id"], document_id=row["document_id"], document_name=row["document_name"],
            page=row["page"], section=row["section"], equipment_model=row["equipment_model"],
            text=row["text"], retrieval_score=round(max(0.0, -raw_rank), 6), source_hash=row["source_hash"],
        ))
    _query_cache[cache_key] = evidence
    _query_cache.move_to_end(cache_key)
    while len(_query_cache) > 128:
        _query_cache.popitem(last=False)
    return evidence


def clear_retrieval_cache() -> int:
    count = len(_query_cache)
    _query_cache.clear()
    return count


def get_evidence_by_ids(evidence_ids: list[str]) -> list[Evidence]:
    if not evidence_ids:
        return []
    placeholders = ",".join("?" for _ in evidence_ids)
    with connect() as connection:
        rows = connection.execute(
            f"""SELECT c.chunk_id, c.document_id, d.document_name, c.page, c.section,
                       c.equipment_model, c.text, c.source_hash
                FROM manual_chunks c JOIN documents d ON d.document_id=c.document_id
                WHERE c.chunk_id IN ({placeholders})""", evidence_ids,
        ).fetchall()
    by_id = {row["chunk_id"]: row for row in rows}
    ordered = []
    for evidence_id in evidence_ids:
        row = by_id.get(evidence_id)
        if row:
            ordered.append(Evidence(id=row["chunk_id"], document_id=row["document_id"], document_name=row["document_name"],
                                    page=row["page"], section=row["section"], equipment_model=row["equipment_model"],
                                    text=row["text"], retrieval_score=0.0, source_hash=row["source_hash"]))
    return ordered


def get_page(document_id: str, page: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT p.document_id,p.page,p.text,p.source_hash,d.document_name FROM manual_pages p "
            "JOIN documents d ON d.document_id=p.document_id WHERE p.document_id=? AND p.page=?",
            (document_id, page),
        ).fetchone()
    return dict(row) if row else None


def list_manuals() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT document_id,document_name,equipment_model,page_count,ingested_at FROM documents ORDER BY document_name"
        ).fetchall()
    return [dict(row) for row in rows]


def supported_finding(query: str, evidence: list[Evidence]) -> tuple[str | None, str]:
    if not evidence:
        return None, "The local manual did not return a source passage for this question. No troubleshooting recommendation is supported."
    evidence_text = " ".join(item.text for item in evidence).casefold()
    query_lower = query.casefold()
    if "e07" in query_lower and "e07" in evidence_text and "feedback" in evidence_text:
        return "Motor-control feedback mismatch (E07)", "The cited manual associates E07 with a motor-control feedback mismatch. This summary does not establish a failed component or authorize repair work."
    if "e03" in query_lower and "e03" in evidence_text and "cooling airflow" in evidence_text:
        return "Cooling airflow alert (E03)", "The cited fault table describes E03 as a cooling airflow alert. The retrieved text does not support a repair action."
    if "relay" in query_lower and "motor relay" in evidence_text:
        return "Motor relay K2 is identified in the component map", "The manual names K2 as the motor relay and provides its relative location. A visual label does not confirm its operating condition."
    return None, "Retrieved text is shown as evidence, but it does not support a specific diagnosis for this question. No procedure was generated."


def local_engine_health(registry: ModelRegistry) -> dict[str, Any]:
    return {"embedding_model": registry.model_state("embedding"), "retrieval": "sqlite_fts5", "semantic_search": False}
