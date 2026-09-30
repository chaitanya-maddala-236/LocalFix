from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(os.getenv("LOCALFIX_ROOT", Path(__file__).resolve().parents[2])).resolve()
DATA_DIR = PROJECT_ROOT / "data"
MANUAL_DIR = DATA_DIR / "manuals"
DB_PATH = Path(os.getenv("LOCALFIX_DATABASE", DATA_DIR / "localfix.sqlite3")).resolve()

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS documents (
  document_id TEXT PRIMARY KEY, document_name TEXT NOT NULL, source_hash TEXT NOT NULL,
  equipment_model TEXT, page_count INTEGER NOT NULL, ingested_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manual_pages (
  document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
  page INTEGER NOT NULL, text TEXT NOT NULL, source_hash TEXT NOT NULL,
  PRIMARY KEY(document_id,page)
);
CREATE TABLE IF NOT EXISTS manual_chunks (
  chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
  page INTEGER NOT NULL, section TEXT NOT NULL DEFAULT '', equipment_model TEXT,
  text TEXT NOT NULL, embedding BLOB, source_hash TEXT NOT NULL, embedding_model TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS manual_chunks_fts USING fts5(
  chunk_id UNINDEXED, document_id UNINDEXED, equipment_model UNINDEXED,
  section UNINDEXED, text, tokenize='unicode61'
);
CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY, equipment_model TEXT NOT NULL, serial_number TEXT,
  fault_code TEXT, diagnosis TEXT, status TEXT NOT NULL, technician TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '', resolution TEXT, created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, simulated INTEGER NOT NULL DEFAULT 0,
  observations TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS case_evidence (
  case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  evidence_id TEXT NOT NULL, document_id TEXT, document_name TEXT, page INTEGER,
  section TEXT, text TEXT, score REAL, source_hash TEXT,
  PRIMARY KEY(case_id,evidence_id)
);
CREATE TABLE IF NOT EXISTS case_steps (
  case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  step_index INTEGER NOT NULL, action TEXT NOT NULL, safety_level TEXT NOT NULL,
  completed INTEGER NOT NULL DEFAULT 0, source_document_id TEXT, source_page INTEGER,
  PRIMARY KEY(case_id,step_index)
);
CREATE INDEX IF NOT EXISTS idx_manual_model_page ON manual_chunks(equipment_model,page);
CREATE INDEX IF NOT EXISTS idx_cases_updated ON cases(updated_at DESC);
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(manual_chunks)")}
        if "embedding_model" not in columns:
            connection.execute("ALTER TABLE manual_chunks ADD COLUMN embedding_model TEXT")
        case_columns = {row["name"] for row in connection.execute("PRAGMA table_info(cases)")}
        if "observations" not in case_columns:
            connection.execute("ALTER TABLE cases ADD COLUMN observations TEXT NOT NULL DEFAULT '[]'")
    seed_demo_manual()


def seed_demo_manual() -> None:
    source_path = MANUAL_DIR / "DemoTech_ACM-4200_Service_Manual_2026.md"
    if not source_path.exists():
        return
    raw = source_path.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    content = raw.decode("utf-8")
    pages = re.split(r"^=== SOURCE PAGE (\d+) ===\s*$", content, flags=re.MULTILINE)
    if len(pages) < 4:
        return
    segments: list[tuple[int, str]] = []
    for index in range(1, len(pages), 2):
        page_number = int(pages[index])
        page_text = pages[index + 1].strip()
        if page_text:
            segments.append((page_number, page_text))
    document_id = "manual_acm4200_demo"
    name = "DemoTech ACM-4200 Service Manual 2026"
    with connect() as connection:
        existing = connection.execute("SELECT source_hash FROM documents WHERE document_id=?", (document_id,)).fetchone()
        if existing and existing["source_hash"] == source_hash:
            return
        if existing:
            connection.execute("DELETE FROM manual_chunks_fts WHERE document_id=?", (document_id,))
            connection.execute("DELETE FROM documents WHERE document_id=?", (document_id,))
        connection.execute("INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,?)", (document_id, name, source_hash, "DemoTech ACM-4200", len(segments), now_iso()))
        for page_number, page_text in segments:
            connection.execute("INSERT INTO manual_pages VALUES (?,?,?,?)", (document_id, page_number, page_text, source_hash))
            section = _section_from_text(page_text, page_number)
            for chunk_index, chunk in enumerate(_chunk_text(page_text)):
                chunk_id = f"{document_id}_p{page_number:03d}_{chunk_index:02d}"
                _insert_chunk(connection, chunk_id, document_id, page_number, section, "DemoTech ACM-4200", chunk, source_hash)


def _section_from_text(text: str, page: int) -> str:
    for line in text.splitlines():
        clean = line.strip().lstrip("#").strip()
        if clean:
            return clean[:160]
    return f"Page {page}"


def _chunk_text(text: str, limit: int = 900, overlap: int = 120) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    result: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + limit, len(clean))
        if end < len(clean):
            boundary = clean.rfind(". ", start + limit // 2, end)
            if boundary > start:
                end = boundary + 1
        result.append(clean[start:end].strip())
        if end >= len(clean):
            break
        start = max(end - overlap, start + 1)
    return result


def _insert_chunk(connection: sqlite3.Connection, chunk_id: str, document_id: str, page: int,
                  section: str, equipment_model: str | None, text: str, source_hash: str) -> None:
    connection.execute("INSERT OR REPLACE INTO manual_chunks "
                       "(chunk_id,document_id,page,section,equipment_model,text,embedding,source_hash,embedding_model) "
                       "VALUES (?,?,?,?,?,?,?,?,NULL)",
                       (chunk_id, document_id, page, section, equipment_model, text, None, source_hash))
    connection.execute("INSERT INTO manual_chunks_fts VALUES (?,?,?,?,?)",
                       (chunk_id, document_id, equipment_model or "", section, text))


def insert_manual_document(document_id: str, document_name: str, source_hash: str,
                           equipment_model: str | None, pages: list[tuple[int, str]]) -> tuple[int, int]:
    chunks_count = 0
    indexed_pages = 0
    with connect() as connection:
        connection.execute("DELETE FROM manual_chunks_fts WHERE document_id=?", (document_id,))
        connection.execute("DELETE FROM documents WHERE document_id=?", (document_id,))
        connection.execute("INSERT INTO documents VALUES (?,?,?,?,?,?)",
                           (document_id, document_name, source_hash, equipment_model, len(pages), now_iso()))
        for page_number, page_text in pages:
            connection.execute("INSERT INTO manual_pages VALUES (?,?,?,?)", (document_id, page_number, page_text, source_hash))
            if not page_text.strip():
                continue
            indexed_pages += 1
            section = _section_from_text(page_text, page_number)
            for chunk_index, chunk in enumerate(_chunk_text(page_text)):
                chunk_id = f"{document_id}_p{page_number:04d}_{chunk_index:02d}"
                _insert_chunk(connection, chunk_id, document_id, page_number, section, equipment_model, chunk, source_hash)
                chunks_count += 1
    return indexed_pages, chunks_count
