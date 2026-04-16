"""
SQLite-backed retrieval store used as a first grounding layer.

Replaces the previous flat-JSON implementation to avoid full-file reads and
writes on every operation. Uses FTS5 for keyword search when available,
falling back to a LIKE scan otherwise.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from llm_core.schemas import EvidenceChunk

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parents[2] / "career_profile.db"
_LEGACY_JSON_PATH = Path(__file__).resolve().parents[2] / "llm_retrieval_store.json"

_schema_ensured: bool = False


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema() -> None:
    """Create evidence_chunks table and FTS5 index on first use."""
    global _schema_ensured
    if _schema_ensured:
        return
    with _get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS evidence_chunks (
                chunk_id    TEXT NOT NULL,
                index_name  TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT '',
                source_id   TEXT NOT NULL DEFAULT '',
                section     TEXT NOT NULL DEFAULT '',
                text        TEXT NOT NULL DEFAULT '',
                score       REAL NOT NULL DEFAULT 0.0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (index_name, chunk_id)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS evidence_chunks_fts
            USING fts5(
                chunk_id UNINDEXED,
                index_name UNINDEXED,
                text,
                content='evidence_chunks',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS evidence_chunks_ai
            AFTER INSERT ON evidence_chunks BEGIN
                INSERT INTO evidence_chunks_fts(rowid, chunk_id, index_name, text)
                VALUES (new.rowid, new.chunk_id, new.index_name, new.text);
            END;

            CREATE TRIGGER IF NOT EXISTS evidence_chunks_ad
            AFTER DELETE ON evidence_chunks BEGIN
                INSERT INTO evidence_chunks_fts(evidence_chunks_fts, rowid, chunk_id, index_name, text)
                VALUES ('delete', old.rowid, old.chunk_id, old.index_name, old.text);
            END;

            CREATE TRIGGER IF NOT EXISTS evidence_chunks_au
            AFTER UPDATE ON evidence_chunks BEGIN
                INSERT INTO evidence_chunks_fts(evidence_chunks_fts, rowid, chunk_id, index_name, text)
                VALUES ('delete', old.rowid, old.chunk_id, old.index_name, old.text);
                INSERT INTO evidence_chunks_fts(rowid, chunk_id, index_name, text)
                VALUES (new.rowid, new.chunk_id, new.index_name, new.text);
            END;
            """
        )
    _schema_ensured = True
    _migrate_legacy_json()


def _migrate_legacy_json() -> None:
    """One-time migration: import any existing JSON store data then remove the file."""
    if not _LEGACY_JSON_PATH.exists():
        return
    try:
        raw = json.loads(_LEGACY_JSON_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    for index_name, rows in raw.items():
        chunks = [
            EvidenceChunk(
                chunk_id=r.get("chunk_id", ""),
                source_type=r.get("source_type", ""),
                source_id=r.get("source_id", ""),
                section=r.get("section", ""),
                text=r.get("text", ""),
                score=float(r.get("score", 0.0) or 0.0),
                metadata=r.get("metadata", {}) or {},
            )
            for r in rows
            if r.get("chunk_id") and r.get("text")
        ]
        if chunks:
            put_chunks(index_name, chunks)

    try:
        _LEGACY_JSON_PATH.unlink()
        logger.info("Migrated retrieval store from JSON to SQLite and removed legacy file.")
    except OSError:
        logger.warning("Could not remove legacy llm_retrieval_store.json after migration.")


def put_chunks(index_name: str, chunks: list[EvidenceChunk]) -> None:
    """Upsert chunks into an index."""
    _ensure_schema()
    with _get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO evidence_chunks
                (chunk_id, index_name, source_type, source_id, section, text, score, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(index_name, chunk_id) DO UPDATE SET
                source_type   = excluded.source_type,
                source_id     = excluded.source_id,
                section       = excluded.section,
                text          = excluded.text,
                score         = excluded.score,
                metadata_json = excluded.metadata_json
            """,
            [
                (
                    chunk.chunk_id,
                    index_name,
                    chunk.source_type,
                    chunk.source_id,
                    chunk.section,
                    chunk.text,
                    chunk.score,
                    json.dumps(chunk.metadata),
                )
                for chunk in chunks
            ],
        )


def get_chunks(index_name: str) -> list[EvidenceChunk]:
    """Return all chunks for an index."""
    _ensure_schema()
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM evidence_chunks WHERE index_name = ?", (index_name,)
        ).fetchall()
    return [_row_to_chunk(row) for row in rows]


def search_chunks(index_name: str, query: str, limit: int = 5) -> list[EvidenceChunk]:
    """Keyword search using FTS5, ranked by hit count."""
    _ensure_schema()
    query_terms = [t for t in query.lower().split() if t]
    if not query_terms:
        return []

    with _get_connection() as conn:
        # Check if FTS5 is available
        has_fts = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_chunks_fts'"
        ).fetchone() is not None

        if has_fts:
            # Wrap each token in double-quotes so FTS5 treats them as phrase
            # literals, preventing special FTS5 characters from acting as operators.
            fts_query = " OR ".join(f'"{t}"' for t in query_terms)
            rows = conn.execute(
                """
                SELECT ec.*, fts.rank AS fts_rank
                FROM evidence_chunks_fts fts
                JOIN evidence_chunks ec
                  ON ec.rowid = fts.rowid
                WHERE evidence_chunks_fts MATCH ?
                  AND ec.index_name = ?
                ORDER BY fts.rank
                LIMIT ?
                """,
                (fts_query, index_name, limit),
            ).fetchall()
        else:
            # Fallback: load all and score in Python
            all_rows = conn.execute(
                "SELECT * FROM evidence_chunks WHERE index_name = ?", (index_name,)
            ).fetchall()
            scored = []
            for row in all_rows:
                text_lower = (row["text"] or "").lower()
                score = sum(1 for t in query_terms if t in text_lower)
                if score > 0:
                    scored.append((score, row))
            scored.sort(key=lambda x: x[0], reverse=True)
            rows = [r for _, r in scored[:limit]]

    return [
        EvidenceChunk(
            chunk_id=row["chunk_id"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            section=row["section"],
            text=row["text"],
            score=float(sum(1 for t in query_terms if t in (row["text"] or "").lower())),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
        for row in rows
    ]


def clear_store(index_name: str | None = None) -> None:
    """Clear one index or the entire store."""
    _ensure_schema()
    with _get_connection() as conn:
        if index_name is None:
            conn.execute("DELETE FROM evidence_chunks")
        else:
            conn.execute(
                "DELETE FROM evidence_chunks WHERE index_name = ?", (index_name,)
            )


def _row_to_chunk(row: sqlite3.Row) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=row["chunk_id"],
        source_type=row["source_type"],
        source_id=row["source_id"],
        section=row["section"],
        text=row["text"],
        score=float(row["score"]),
        metadata=json.loads(row["metadata_json"] or "{}"),
    )
