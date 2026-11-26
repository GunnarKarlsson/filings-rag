"""Parse → chunk → SQLite catalog (embeddings are a later step)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from filings_rag.blueprint.io import load_blueprint
from filings_rag.blueprint.model import Blueprint
from filings_rag.chunking import chunks_for_filing
from filings_rag.config import BLUEPRINT_PATH, CATALOG_PATH, FILINGS_10K_DIR
from filings_rag.parse import list_filing_paths, parse_filing
from filings_rag.store import Catalog


@dataclass(frozen=True)
class IngestResult:
    mode: str
    filing_count: int
    chunk_count: int
    catalog_path: Path


def _source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ingest_filings(
    *,
    filings_dir: Path = FILINGS_10K_DIR,
    blueprint_path: Path = BLUEPRINT_PATH,
    catalog_path: Path = CATALOG_PATH,
    company: str | None = None,
    skip_embed: bool = True,
) -> IngestResult:
    if not skip_embed:
        raise ValueError(
            "Embedding is not wired yet. Re-run with skip_embed=True "
            "(CLI: filings-rag ingest --skip-embed)."
        )
    if not blueprint_path.is_file():
        raise FileNotFoundError(f"Missing blueprint: {blueprint_path}")

    blueprint: Blueprint = load_blueprint(blueprint_path)
    paths = list_filing_paths(filings_dir)
    if company:
        paths = [p for p in paths if p.parts[-3] == company]
    if not paths:
        raise FileNotFoundError(f"No 10-K HTML under {filings_dir}")

    started = datetime.now(timezone.utc).isoformat()
    total_chunks = 0
    with Catalog(catalog_path) as catalog:
        for path in paths:
            parsed = parse_filing(path, blueprint)
            chunks = chunks_for_filing(parsed, blueprint)
            if not chunks:
                continue
            first = chunks[0]
            catalog.replace_filing_chunks(
                company_key=first.company_key,
                accession_number=first.accession_number,
                cik=first.cik,
                company_name=first.company_name,
                form=first.form,
                fiscal_year=first.fiscal_year,
                sec_url=first.sec_url,
                path=str(path),
                source_hash=_source_hash(path),
                chunks=chunks,
            )
            total_chunks += len(chunks)

        catalog.record_run(
            mode="skip_embed",
            filing_count=len(paths),
            chunk_count=total_chunks,
            started_at=started,
        )

    return IngestResult(
        mode="skip_embed",
        filing_count=len(paths),
        chunk_count=total_chunks,
        catalog_path=catalog_path,
    )
