"""SQLite catalog + ingest --skip-embed on real filings."""

from __future__ import annotations

from pathlib import Path

import pytest

from filings_rag.config import BLUEPRINT_PATH, FILINGS_10K_DIR
from filings_rag.ingest import ingest_filings
from filings_rag.store import Catalog


@pytest.fixture()
def catalog_path(tmp_path: Path) -> Path:
    return tmp_path / "catalog.sqlite"


def test_ingest_skip_embed_writes_all_companies(catalog_path: Path) -> None:
    if not any(FILINGS_10K_DIR.glob("*/*/10k.htm")):
        pytest.fail("Need data/10k/; run ./scripts/download_10k.sh")

    result = ingest_filings(
        filings_dir=FILINGS_10K_DIR,
        blueprint_path=BLUEPRINT_PATH,
        catalog_path=catalog_path,
        skip_embed=True,
    )
    assert result.filing_count >= 7
    assert result.chunk_count > 100
    assert catalog_path.is_file()

    with Catalog(catalog_path) as catalog:
        stats = catalog.stats()
        assert stats.filings == result.filing_count
        assert stats.chunks == result.chunk_count
        assert stats.companies == result.filing_count
        assert stats.last_run_mode == "skip_embed"

        nvidia = catalog.fetch_chunks(
            company_key="nvidia", section_id="fs_income", limit=5
        )
        assert nvidia
        assert "Revenue" in nvidia[0]["preview"] or "revenue" in nvidia[0]["preview"].lower()


def test_reingest_is_idempotent(catalog_path: Path) -> None:
    if not any(FILINGS_10K_DIR.glob("nvidia/*/10k.htm")):
        pytest.fail("Need nvidia 10-K; run ./scripts/download_10k.sh")

    first = ingest_filings(
        catalog_path=catalog_path,
        company="nvidia",
        skip_embed=True,
    )
    second = ingest_filings(
        catalog_path=catalog_path,
        company="nvidia",
        skip_embed=True,
    )
    assert first.chunk_count == second.chunk_count
    assert first.chunk_count > 0

    with Catalog(catalog_path) as catalog:
        stats = catalog.stats()
        assert stats.filings == 1
        assert stats.chunks == second.chunk_count
        # Two run records (first + second).
        assert stats.last_run_mode == "skip_embed"


def test_ingest_without_skip_embed_raises(catalog_path: Path) -> None:
    with pytest.raises(ValueError, match="Embedding is not wired"):
        ingest_filings(catalog_path=catalog_path, skip_embed=False)


def test_clear_catalog_removes_db_files(catalog_path: Path) -> None:
    from filings_rag.store import clear_catalog

    catalog_path.write_text("placeholder", encoding="utf-8")
    wal = Path(f"{catalog_path}-wal")
    shm = Path(f"{catalog_path}-shm")
    wal.write_text("w", encoding="utf-8")
    shm.write_text("s", encoding="utf-8")

    removed = clear_catalog(catalog_path)
    assert catalog_path in removed
    assert wal in removed
    assert shm in removed
    assert not catalog_path.exists()
    assert clear_catalog(catalog_path) == ()
