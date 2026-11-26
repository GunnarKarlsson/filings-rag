"""SQLite catalog for filing and chunk rows (no vectors yet)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from filings_rag.chunking.model import Chunk

# Table names are singular: each row is one ingest_run / filing / chunk.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    mode TEXT NOT NULL,
    filing_count INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS filing (
    company_key TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    cik TEXT NOT NULL,
    company_name TEXT NOT NULL,
    form TEXT NOT NULL,
    fiscal_year INTEGER,
    sec_url TEXT NOT NULL,
    path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (company_key, accession_number)
);

CREATE TABLE IF NOT EXISTS chunk (
    chunk_id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    cik TEXT NOT NULL,
    company_name TEXT NOT NULL,
    form TEXT NOT NULL,
    fiscal_year INTEGER,
    sec_url TEXT NOT NULL,
    section_id TEXT NOT NULL,
    item TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE (company_key, accession_number, section_id, chunk_index),
    FOREIGN KEY (company_key, accession_number)
        REFERENCES filing (company_key, accession_number)
);

CREATE INDEX IF NOT EXISTS idx_chunk_company ON chunk (company_key);
CREATE INDEX IF NOT EXISTS idx_chunk_section ON chunk (section_id);
CREATE INDEX IF NOT EXISTS idx_chunk_item ON chunk (item);
"""


@dataclass(frozen=True)
class CatalogStats:
    filings: int
    chunks: int
    companies: int
    last_run_mode: str | None
    last_run_at: str | None


def clear_catalog(path: Path) -> tuple[Path, ...]:
    """
    Delete the SQLite catalog file and any WAL/SHM sidecars.

    Returns the paths that were removed. Does not touch data/10k/.
    """
    removed: list[Path] = []
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        if candidate.is_file():
            candidate.unlink()
            removed.append(candidate)
    return tuple(removed)


class Catalog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Catalog:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def replace_filing_chunks(
        self,
        *,
        company_key: str,
        accession_number: str,
        cik: str,
        company_name: str,
        form: str,
        fiscal_year: int | None,
        sec_url: str,
        path: str,
        source_hash: str,
        chunks: list[Chunk],
    ) -> None:
        """Idempotent write: drop prior chunks for this filing, then insert."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "DELETE FROM chunk WHERE company_key = ? AND accession_number = ?",
            (company_key, accession_number),
        )
        self._conn.execute(
            """
            INSERT INTO filing (
                company_key, accession_number, cik, company_name, form,
                fiscal_year, sec_url, path, source_hash, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_key, accession_number) DO UPDATE SET
                cik = excluded.cik,
                company_name = excluded.company_name,
                form = excluded.form,
                fiscal_year = excluded.fiscal_year,
                sec_url = excluded.sec_url,
                path = excluded.path,
                source_hash = excluded.source_hash,
                ingested_at = excluded.ingested_at
            """,
            (
                company_key,
                accession_number,
                cik,
                company_name,
                form,
                fiscal_year,
                sec_url,
                path,
                source_hash,
                now,
            ),
        )
        self._conn.executemany(
            """
            INSERT INTO chunk (
                chunk_id, company_key, accession_number, cik, company_name,
                form, fiscal_year, sec_url, section_id, item, chunk_index,
                start_offset, end_offset, text, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    c.chunk_id,
                    c.company_key,
                    c.accession_number,
                    c.cik,
                    c.company_name,
                    c.form,
                    c.fiscal_year,
                    c.sec_url,
                    c.section_id,
                    c.item,
                    c.chunk_index,
                    c.start_offset,
                    c.end_offset,
                    c.text,
                    c.content_hash,
                )
                for c in chunks
            ],
        )
        self._conn.commit()

    def record_run(
        self,
        *,
        mode: str,
        filing_count: int,
        chunk_count: int,
        started_at: str,
    ) -> None:
        finished = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO ingest_run (
                started_at, finished_at, mode, filing_count, chunk_count
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (started_at, finished, mode, filing_count, chunk_count),
        )
        self._conn.commit()

    def stats(self) -> CatalogStats:
        filings = self._conn.execute("SELECT COUNT(*) FROM filing").fetchone()[0]
        chunks = self._conn.execute("SELECT COUNT(*) FROM chunk").fetchone()[0]
        companies = self._conn.execute(
            "SELECT COUNT(DISTINCT company_key) FROM filing"
        ).fetchone()[0]
        row = self._conn.execute(
            """
            SELECT mode, finished_at FROM ingest_run
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        return CatalogStats(
            filings=int(filings),
            chunks=int(chunks),
            companies=int(companies),
            last_run_mode=None if row is None else str(row["mode"]),
            last_run_at=None if row is None else str(row["finished_at"]),
        )

    def count_chunks_for(self, company_key: str, accession_number: str) -> int:
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS n FROM chunk
            WHERE company_key = ? AND accession_number = ?
            """,
            (company_key, accession_number),
        ).fetchone()
        return int(row["n"])

    def fetch_chunks(
        self,
        *,
        company_key: str | None = None,
        section_id: str | None = None,
        limit: int = 20,
    ) -> list[sqlite3.Row]:
        clauses: list[str] = []
        params: list[object] = []
        if company_key:
            clauses.append("company_key = ?")
            params.append(company_key)
        if section_id:
            clauses.append("section_id = ?")
            params.append(section_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT chunk_id, company_key, section_id, item, chunk_index,
                   length(text) AS text_len, substr(text, 1, 120) AS preview
            FROM chunk
            {where}
            ORDER BY company_key, section_id, chunk_index
            LIMIT ?
        """
        params.append(limit)
        return list(self._conn.execute(sql, params))
