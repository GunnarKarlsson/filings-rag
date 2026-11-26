"""Chunking on real parsed 10-K sections."""

from __future__ import annotations

import pytest

from filings_rag.blueprint.io import load_blueprint
from filings_rag.chunking import chunks_for_filing, split_text
from filings_rag.chunking.split import DEFAULT_CHUNK_CHARS
from filings_rag.config import BLUEPRINT_PATH, FILINGS_10K_DIR
from filings_rag.parse import list_filing_paths, parse_filing


def test_split_text_respects_size_and_overlap() -> None:
    text = ("Paragraph one about revenue.\n\n" * 40) + ("More words here. " * 80)
    parts = split_text(text, chunk_chars=500, overlap_chars=50)
    assert len(parts) >= 2
    for start, end, piece in parts:
        assert 0 <= start < end <= len(text)
        assert piece == text[start:end]
        assert len(piece) <= 500 + 20  # allow small boundary slack via separators
    # Overlap: next window starts before the previous window ends.
    (_s0, e0, _), (s1, _e1, _) = parts[0], parts[1]
    assert s1 < e0


def test_split_short_text_is_single_chunk() -> None:
    parts = split_text("short", chunk_chars=100, overlap_chars=10)
    assert parts == [(0, 5, "short")]


@pytest.fixture(scope="module")
def all_company_chunks() -> dict[str, list]:
    if not any(FILINGS_10K_DIR.glob("*/*/10k.htm")):
        pytest.fail("Need data/10k/; run ./scripts/download_10k.sh")
    blueprint = load_blueprint(BLUEPRINT_PATH)
    out: dict[str, list] = {}
    for path in list_filing_paths(FILINGS_10K_DIR):
        parsed = parse_filing(path, blueprint)
        out[parsed.company_key] = chunks_for_filing(parsed, blueprint)
    return out


def test_every_filing_produces_chunks(all_company_chunks: dict[str, list]) -> None:
    assert len(all_company_chunks) >= 7
    for company, chunks in all_company_chunks.items():
        assert chunks, f"{company}: no chunks"
        assert all(c.company_key == company for c in chunks)
        assert all(c.form == "10-K" for c in chunks)
        assert all(c.text.strip() for c in chunks)
        assert all(c.accession_number for c in chunks)


def test_income_statement_appears_in_chunks(
    all_company_chunks: dict[str, list],
) -> None:
    for company, chunks in all_company_chunks.items():
        income = [c for c in chunks if c.section_id == "fs_income"]
        assert income, f"{company}: missing fs_income chunks"
        blob = " ".join(c.text.lower() for c in income)
        assert any(
            key in blob
            for key in ("revenue", "revenues", "net sales", "net product sales")
        ), f"{company}: income chunks lack revenue/sales"


def test_narrative_sections_are_split_when_long(
    all_company_chunks: dict[str, list],
) -> None:
    # At least one company should have a multi-chunk Item 1A (risk factors).
    multi = []
    for company, chunks in all_company_chunks.items():
        risk = [c for c in chunks if c.section_id == "item_1a"]
        if len(risk) >= 2:
            multi.append(company)
            assert risk[0].chunk_index == 0
            assert risk[1].chunk_index == 1
            assert all(len(c.text) <= DEFAULT_CHUNK_CHARS + 50 for c in risk)
    assert multi, "expected Item 1A to split on at least one filing"


def test_print_chunk_samples_for_human_check(
    all_company_chunks: dict[str, list],
) -> None:
    """Print a few chunk previews. Run with pytest -s to read them."""
    for company in sorted(all_company_chunks):
        chunks = all_company_chunks[company]
        income = next(c for c in chunks if c.section_id == "fs_income")
        print(f"\n=== {company}: {len(chunks)} chunks ===")
        print(
            f"fs_income chunk0 ({len(income.text)} chars): "
            f"{income.text[:240].replace(chr(10), ' | ')}"
        )
