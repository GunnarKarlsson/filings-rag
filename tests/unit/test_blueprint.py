"""Blueprint load + required-section coverage on real local 10-Ks."""

from pathlib import Path

import pytest

from filings_rag.blueprint import (
    build_blueprint,
    coverage_report,
    load_blueprint,
    save_blueprint,
)
from filings_rag.blueprint.detect import detect_item_headers_in_file
from filings_rag.config import BLUEPRINT_PATH, FILINGS_10K_DIR

SOURCE_COMPANIES = ("nvidia", "apple", "microsoft")


def _has_filing(company: str) -> bool:
    return any(FILINGS_10K_DIR.glob(f"{company}/*/10k.htm"))


@pytest.fixture(scope="module")
def require_corpus() -> None:
    missing = [c for c in SOURCE_COMPANIES if not _has_filing(c)]
    if missing:
        pytest.fail(
            f"Missing local 10-K HTML for {missing}; run ./scripts/download_10k.sh"
        )


def test_detect_headers_finds_core_items(require_corpus: None) -> None:
    path = next(FILINGS_10K_DIR.glob("nvidia/*/10k.htm"))
    headers = detect_item_headers_in_file(path)
    for item in ("1", "1A", "7", "8"):
        assert item in headers, f"nvidia missing Item {item}: {sorted(headers)}"


def test_build_and_load_blueprint_roundtrip(
    require_corpus: None, tmp_path: Path
) -> None:
    blueprint = build_blueprint(list(SOURCE_COMPANIES))
    assert set(blueprint.source_companies) == set(SOURCE_COMPANIES)
    assert any(s.id == "item_1a" and s.required for s in blueprint.sections)
    assert any(s.id == "item_6" and not s.required for s in blueprint.sections)
    hotspot_ids = {
        "fs_auditor_report",
        "fs_income",
        "fs_comprehensive_income",
        "fs_balance_sheet",
        "fs_equity",
        "fs_cash_flows",
        "fs_notes",
    }
    by_id = blueprint.by_id()
    for hid in hotspot_ids:
        assert hid in by_id
        assert by_id[hid].parent == "item_8"
        assert by_id[hid].required
    assert by_id["fs_schedule_ii"].parent == "item_15"

    out = tmp_path / "10k_sections.yaml"
    save_blueprint(blueprint, out)
    loaded = load_blueprint(out)
    assert loaded.source_companies == blueprint.source_companies
    assert [s.id for s in loaded.sections] == [s.id for s in blueprint.sections]


def test_financial_hotspots_found_in_corpus(
    require_corpus: None,
) -> None:
    """Required statement titles appear in a sample of local 10-Ks."""
    blueprint = build_blueprint(["nvidia", "apple", "microsoft"])
    report = coverage_report(blueprint, ["nvidia", "apple", "microsoft"])
    for company, info in report.items():
        missing_fs = [m for m in info["missing"] if m.startswith("fs_") and m != "fs_schedule_ii"]
        assert missing_fs == [], f"{company} missing financial hotspots: {missing_fs}"


def test_pointer_layout_toc_income_link_resolves_to_revenue_table(
    require_corpus: None,
) -> None:
    """When Item 15(a)(1) uses #fragment links (pointer/F-page layout), follow them."""
    import re

    from bs4 import BeautifulSoup

    path = next(FILINGS_10K_DIR.glob("nvidia/*/10k.htm"))
    soup = BeautifulSoup(
        path.read_text(encoding="utf-8", errors="replace"), "html.parser"
    )
    link = None
    for anchor in soup.find_all("a", href=True):
        text = " ".join(anchor.get_text(" ", strip=True).split())
        if re.search(r"(?i)consolidated statements of income", text) and re.search(
            r"(?i)years ended", text
        ):
            link = anchor
            break
    assert link is not None, "NVIDIA Item 15 TOC link for income statement not found"
    href = link["href"]
    assert "#" in href, href
    frag = href.split("#", 1)[1]
    target = soup.find(id=frag) or soup.find(attrs={"name": frag})
    assert target is not None, f"missing target for {href}"
    table = target.find_next("table")
    assert table is not None
    table_text = " ".join(table.get_text(" ", strip=True).split())
    assert "Revenue" in table_text
    assert "215,938" in table_text or "215938" in table_text.replace(",", "")


def test_required_sections_covered_in_source_filings(require_corpus: None) -> None:
    blueprint = build_blueprint(list(SOURCE_COMPANIES))
    report = coverage_report(blueprint, list(SOURCE_COMPANIES))
    for company, result in report.items():
        assert result["missing"] == [], (
            f"{company} missing required sections: {result['missing']}"
        )


def test_committed_blueprint_file_loads_when_present() -> None:
    if not BLUEPRINT_PATH.is_file():
        pytest.skip("blueprint file not written yet; run filings-rag blueprint")
    blueprint = load_blueprint(BLUEPRINT_PATH)
    assert blueprint.sections
    assert "nvidia" in blueprint.source_companies
