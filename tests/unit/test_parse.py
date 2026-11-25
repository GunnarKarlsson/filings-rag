"""Parse all local 10-Ks into blueprint sections (including financial hotspots)."""

from __future__ import annotations

import pytest

from filings_rag.blueprint.io import load_blueprint
from filings_rag.config import BLUEPRINT_PATH, FILINGS_10K_DIR
from filings_rag.parse import format_rows, list_filing_paths, parse_filing
from filings_rag.parse.model import ParsedFiling

# Statement grids every filing must yield with enough rows for inspection.
REQUIRED_TABLE_HOTSPOTS = (
    "fs_income",
    "fs_comprehensive_income",
    "fs_balance_sheet",
    "fs_equity",
    "fs_cash_flows",
)

REQUIRED_NARRATIVE = (
    "item_1",
    "item_1a",
    "item_7",
    "item_8",
    "fs_auditor_report",
    "fs_notes",
)


def _all_companies() -> list[str]:
    return sorted({p.parts[-3] for p in FILINGS_10K_DIR.glob("*/*/10k.htm")})


@pytest.fixture(scope="module")
def require_full_corpus() -> list[str]:
    companies = _all_companies()
    if len(companies) < 2:
        pytest.fail(
            "Need local 10-K HTML under data/10k/; run ./scripts/download_10k.sh"
        )
    return companies


@pytest.fixture(scope="module")
def parsed_filings(require_full_corpus: list[str]) -> dict[str, ParsedFiling]:
    blueprint = load_blueprint(BLUEPRINT_PATH)
    out: dict[str, ParsedFiling] = {}
    for path in list_filing_paths(FILINGS_10K_DIR):
        parsed = parse_filing(path, blueprint)
        out[parsed.company_key] = parsed
    assert set(out) == set(require_full_corpus)
    return out


def test_corpus_has_every_listed_company(require_full_corpus: list[str]) -> None:
    # Guard: tests intentionally run on the full downloaded set, not a subset.
    assert "nvidia" in require_full_corpus
    assert "apple" in require_full_corpus
    assert len(require_full_corpus) >= 7


@pytest.mark.parametrize("company", _all_companies() or ["__missing__"])
def test_required_item_sections_extracted(
    company: str, parsed_filings: dict[str, ParsedFiling]
) -> None:
    if company == "__missing__":
        pytest.fail("no filings in data/10k/")
    parsed = parsed_filings[company]
    by_id = parsed.by_id()
    for section_id in REQUIRED_NARRATIVE:
        sec = by_id.get(section_id)
        assert sec is not None, f"{company}: missing {section_id}"
        assert len(sec.text.strip()) >= 40, f"{company}: empty {section_id}"


@pytest.mark.parametrize("company", _all_companies() or ["__missing__"])
def test_required_financial_tables_extracted(
    company: str, parsed_filings: dict[str, ParsedFiling]
) -> None:
    if company == "__missing__":
        pytest.fail("no filings in data/10k/")
    parsed = parsed_filings[company]
    by_id = parsed.by_id()
    for section_id in REQUIRED_TABLE_HOTSPOTS:
        sec = by_id.get(section_id)
        assert sec is not None, f"{company}: missing {section_id}"
        table = sec.primary_table()
        assert table is not None, f"{company}: no table for {section_id}"
        assert len(table.rows) >= 5, (
            f"{company}: {section_id} only {len(table.rows)} rows"
        )


@pytest.mark.parametrize("company", _all_companies() or ["__missing__"])
def test_income_statement_has_revenue_line(
    company: str, parsed_filings: dict[str, ParsedFiling]
) -> None:
    if company == "__missing__":
        pytest.fail("no filings in data/10k/")
    sec = parsed_filings[company].get("fs_income")
    assert sec is not None and sec.primary_table() is not None
    blob = " ".join(" ".join(r) for r in sec.primary_table().rows).lower()
    assert any(
        key in blob
        for key in ("revenue", "revenues", "net sales", "net product sales")
    ), f"{company}: income table missing a revenue/sales line"


@pytest.mark.parametrize("company", _all_companies() or ["__missing__"])
def test_balance_sheet_has_total_assets(
    company: str, parsed_filings: dict[str, ParsedFiling]
) -> None:
    if company == "__missing__":
        pytest.fail("no filings in data/10k/")
    sec = parsed_filings[company].get("fs_balance_sheet")
    assert sec is not None and sec.primary_table() is not None
    blob = " ".join(" ".join(r) for r in sec.primary_table().rows).lower()
    assert "total assets" in blob, f"{company}: balance sheet missing total assets"


@pytest.mark.parametrize("company", _all_companies() or ["__missing__"])
def test_cash_flows_has_operating_section(
    company: str, parsed_filings: dict[str, ParsedFiling]
) -> None:
    if company == "__missing__":
        pytest.fail("no filings in data/10k/")
    sec = parsed_filings[company].get("fs_cash_flows")
    assert sec is not None and sec.primary_table() is not None
    blob = " ".join(" ".join(r) for r in sec.primary_table().rows).lower()
    assert "operating" in blob, f"{company}: cash-flow table missing operating section"
    assert "investing" in blob or "financing" in blob


def test_print_statement_previews_for_human_check(
    parsed_filings: dict[str, ParsedFiling],
) -> None:
    """
    Print the first 10 rows of P&L, balance sheet, and cash flows for every
    filing. Run with `pytest -s tests/unit/test_parse.py` to read the tables.
    """
    for company in sorted(parsed_filings):
        parsed = parsed_filings[company]
        print(f"\n{'=' * 72}\n{company}  ({parsed.path})\n{'=' * 72}")
        for section_id, label in (
            ("fs_income", "Profit & loss (income / operations)"),
            ("fs_balance_sheet", "Balance sheet"),
            ("fs_cash_flows", "Cash flows"),
        ):
            sec = parsed.get(section_id)
            assert sec is not None and sec.primary_table() is not None
            rows = sec.primary_table().preview_rows(10)
            print(f"\n--- {label} [{section_id}] ({len(sec.primary_table().rows)} rows) ---")
            print(format_rows(rows))
            assert len(rows) == min(10, len(sec.primary_table().rows))
