"""Build a section blueprint from 2–3 real local 10-Ks."""

from __future__ import annotations

import re
from pathlib import Path

from filings_rag.blueprint.detect import (
    detect_item_headers_in_file,
    find_named_aliases,
    html_to_text,
    item_mentioned_in_text,
    named_section_in_text,
)
from filings_rag.blueprint.model import Blueprint, SectionSpec
from filings_rag.config import FILINGS_10K_DIR

# Canonical Form 10-K item order (SEC structure). Titles refined from filings.
_CANONICAL: tuple[tuple[str, str, bool], ...] = (
    ("1", "Business", True),
    ("1A", "Risk Factors", True),
    ("1B", "Unresolved Staff Comments", True),
    ("1C", "Cybersecurity", True),
    ("2", "Properties", True),
    ("3", "Legal Proceedings", True),
    ("4", "Mine Safety Disclosures", True),
    (
        "5",
        "Market for Registrant's Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities",
        True,
    ),
    ("6", "[Reserved]", False),
    (
        "7",
        "Management's Discussion and Analysis of Financial Condition and Results of Operations",
        True,
    ),
    ("7A", "Quantitative and Qualitative Disclosures About Market Risk", True),
    ("8", "Financial Statements and Supplementary Data", True),
    (
        "9",
        "Changes in and Disagreements with Accountants on Accounting and Financial Disclosure",
        True,
    ),
    ("9A", "Controls and Procedures", True),
    ("9B", "Other Information", True),
    ("9C", "Disclosure Regarding Foreign Jurisdictions that Prevent Inspections", True),
    ("10", "Directors, Executive Officers and Corporate Governance", True),
    ("11", "Executive Compensation", True),
    (
        "12",
        "Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters",
        True,
    ),
    ("13", "Certain Relationships and Related Transactions, and Director Independence", True),
    ("14", "Principal Accountant Fees and Services", True),
    ("15", "Exhibits and Financial Statement Schedules", True),
    ("16", "Form 10-K Summary", True),
)

# Item 8 owns primary statements; Item 15 owns supplemental schedules.
# Parse by title patterns / #fragment TOC links, not by assumed HTML position.
# Each: id, title, required, parent, content, header_patterns, compact_needles
_FINANCIAL_HOTSPOTS: tuple[
    tuple[str, str, bool, str, str, tuple[str, ...], tuple[str, ...]], ...
] = (
    (
        "fs_auditor_report",
        "Report of Independent Registered Public Accounting Firm",
        True,
        "item_8",
        "narrative",
        (r"(?i)Report of Independent Registered Public Accounting Firm",),
        ("reportofindependentregisteredpublicaccountingfirm",),
    ),
    (
        "fs_income",
        "Consolidated Statements of Income",
        True,
        "item_8",
        "tables",
        (
            r"(?i)Consolidated Statements? of Income\b",
            r"(?i)Consolidated Statements? of Operations\b",
            r"(?i)\bINCOME STATEMENTS?\b",
        ),
        (
            "consolidatedstatementsofincome",
            "consolidatedstatementsofoperations",
            "incomestatements",
        ),
    ),
    (
        "fs_comprehensive_income",
        "Consolidated Statements of Comprehensive Income",
        True,
        "item_8",
        "tables",
        (
            r"(?i)Consolidated Statements? of Comprehensive Income\b",
            r"(?i)\bCOMPREHENSIVE INCOME STATEMENTS?\b",
        ),
        (
            "consolidatedstatementsofcomprehensiveincome",
            "comprehensiveincomestatements",
        ),
    ),
    (
        "fs_balance_sheet",
        "Consolidated Balance Sheets",
        True,
        "item_8",
        "tables",
        (
            r"(?i)Consolidated Balance Sheets?\b",
            r"(?i)\bBALANCE SHEETS?\b",
        ),
        ("consolidatedbalancesheets", "consolidatedbalancesheet", "balancesheets"),
    ),
    (
        "fs_equity",
        "Consolidated Statements of Shareholders' Equity",
        True,
        "item_8",
        "tables",
        (
            r"(?i)Consolidated Statements? of Shareholders['’]? Equity\b",
            r"(?i)Consolidated Statements? of Stockholders['’]? Equity\b",
            r"(?i)Statements? of Stockholders['’]? Equity\b",
        ),
        (
            "consolidatedstatementsofshareholdersequity",
            "consolidatedstatementsofstockholdersequity",
            "statementsofstockholdersequity",
            "stockholdersequitystatements",
            "shareholdersequitystatements",
        ),
    ),
    (
        "fs_cash_flows",
        "Consolidated Statements of Cash Flows",
        True,
        "item_8",
        "tables",
        (
            r"(?i)Consolidated Statements? of Cash Flows?\b",
            r"(?i)\bCASH FLOWS? STATEMENTS?\b",
            r"(?i)Statements? of Cash Flows?\b",
        ),
        (
            "consolidatedstatementsofcashflows",
            "cashflowsstatements",
            "statementsofcashflows",
        ),
    ),
    (
        "fs_notes",
        "Notes to the Consolidated Financial Statements",
        True,
        "item_8",
        "tables",
        (
            r"(?i)Notes to the Consolidated Financial Statements\b",
            r"(?i)Notes to Consolidated Financial Statements\b",
            r"(?i)Notes to Financial Statements\b",
        ),
        (
            "notestotheconsolidatedfinancialstatements",
            "notestoconsolidatedfinancialstatements",
            "notestofinancialstatements",
        ),
    ),
    (
        "fs_schedule_ii",
        "Schedule II Valuation and Qualifying Accounts",
        False,  # optional; often omitted when covered in Item 8 footnotes
        "item_15",
        "tables",
        (
            r"(?i)Schedule II\b.{0,40}Valuation and Qualifying Accounts",
            r"(?i)Schedule II Valuation and Qualifying Accounts",
        ),
        ("scheduleiivaluationandqualifyingaccounts",),
    ),
)


def _filing_path(company_key: str) -> Path:
    matches = sorted(FILINGS_10K_DIR.glob(f"{company_key}/*/10k.htm"))
    if not matches:
        raise FileNotFoundError(
            f"No 10k.htm for company_key={company_key!r} under {FILINGS_10K_DIR}"
        )
    return matches[0]


def _item_sort_key(item: str) -> tuple[int, str]:
    m = re.match(r"(\d+)([A-C]?)$", item.upper())
    if not m:
        return (999, item)
    return (int(m.group(1)), m.group(2))


def _header_patterns(item: str, title: str) -> tuple[str, ...]:
    esc_item = re.escape(item)
    first_words = " ".join(title.replace("[", "").replace("]", "").split()[:4])
    esc_words = re.escape(first_words) if first_words else ""
    patterns = [
        rf"(?i)\bITEM\s+{esc_item}\s*[.]?\s+{esc_words}",
        rf"(?i)\bITEM\s+{esc_item}\b",
    ]
    return tuple(dict.fromkeys(patterns))


def _section_present(text: str, section: SectionSpec) -> bool:
    if section.parent or section.compact_needles or section.id.startswith("fs_"):
        return named_section_in_text(
            text,
            header_patterns=section.header_patterns,
            compact_needles=section.compact_needles,
        )
    return item_mentioned_in_text(text, section.item)


def build_blueprint(company_keys: list[str]) -> Blueprint:
    per_company_items: dict[str, dict[str, str]] = {}
    per_company_text: dict[str, str] = {}
    for key in company_keys:
        path = _filing_path(key)
        html = path.read_text(encoding="utf-8", errors="replace")
        per_company_text[key] = html_to_text(html)
        per_company_items[key] = detect_item_headers_in_file(path)

    seen_items: set[str] = set()
    for headers in per_company_items.values():
        seen_items.update(headers.keys())

    sections: list[SectionSpec] = []
    for item, default_title, default_required in _CANONICAL:
        aliases: list[str] = []
        for headers in per_company_items.values():
            if item in headers:
                alias = f"Item {item}. {headers[item]}"
                if alias not in aliases:
                    aliases.append(alias)

        required = False if item == "6" else default_required
        sections.append(
            SectionSpec(
                id=f"item_{item.lower()}",
                item=item,
                title=default_title,
                required=required,
                header_patterns=_header_patterns(item, default_title),
                aliases_seen=tuple(aliases),
            )
        )

    for item in sorted(seen_items, key=_item_sort_key):
        if any(s.item == item and s.parent is None for s in sections):
            continue
        titles = [
            per_company_items[c][item]
            for c in company_keys
            if item in per_company_items[c]
        ]
        title = titles[0] if titles else f"Item {item}"
        aliases = [f"Item {item}. {t}" for t in titles]
        sections.append(
            SectionSpec(
                id=f"item_{item.lower()}",
                item=item,
                title=title,
                required=False,
                header_patterns=_header_patterns(item, title),
                aliases_seen=tuple(aliases),
            )
        )

    # Item number follows SEC ownership (8 vs 15). Insert after parent ITEM.
    hotspot_specs: list[SectionSpec] = []
    for (
        section_id,
        title,
        required,
        parent,
        content,
        patterns,
        needles,
    ) in _FINANCIAL_HOTSPOTS:
        aliases: list[str] = []
        for key in company_keys:
            aliases.extend(find_named_aliases(per_company_text[key], patterns))
        aliases = list(dict.fromkeys(aliases))
        hotspot_specs.append(
            SectionSpec(
                id=section_id,
                item="15" if parent == "item_15" else "8",
                title=title,
                required=required,
                header_patterns=patterns,
                aliases_seen=tuple(aliases),
                parent=parent,
                compact_needles=needles,
                content=content,
            )
        )

    by_parent: dict[str, list[SectionSpec]] = {}
    for spec in hotspot_specs:
        assert spec.parent is not None
        by_parent.setdefault(spec.parent, []).append(spec)

    out: list[SectionSpec] = []
    for section in sections:
        out.append(section)
        out.extend(by_parent.pop(section.id, []))
    for leftover in by_parent.values():
        out.extend(leftover)

    notes = (
        "Parsing rules for Form 10-K HTML. "
        "SEC item numbers are fixed (Regulation S-K): Item 8 = Financial "
        "Statements and Supplementary Data; Item 15 = Exhibits and Financial "
        "Statement Schedules. Primary statements (auditor report, income/"
        "operations, comprehensive income, balance sheet, equity, cash flows, "
        "notes) satisfy Item 8. Item 15(a)(1) is an index of those statements; "
        "supplemental schedules (e.g. Schedule II), when present, belong to "
        "Item 15. "
        "Detect ITEM section starts with header_patterns on real ITEM headings; "
        "ignore narrative cross-references (e.g. 'see Item 1A of this Form'). "
        "Item 6 is [Reserved] and not required. "
        "For statement hotspots: match header_patterns / compact_needles on "
        "statement titles—not on a fixed byte offset under an ITEM heading. "
        "If a TOC or index entry for a statement is an href with a #fragment, "
        "resolve that fragment and take the linked body (usually the HTML "
        "table); do not treat TOC page numbers as the payload. "
        "content=tables means table-aware extraction; content=narrative means "
        "prose. header_patterns include known title wordings (Operations vs "
        "Income, Stockholders vs Shareholders). compact_needles match text "
        "when HTML splits words across tags. "
        "source_companies lists filings used to harvest aliases_seen only."
    )
    return Blueprint(
        source_companies=tuple(company_keys),
        notes=notes,
        sections=tuple(out),
    )


def coverage_report(
    blueprint: Blueprint,
    company_keys: list[str] | None = None,
) -> dict[str, dict[str, list[str]]]:
    """For each company, list required section ids found vs missing."""
    keys = list(company_keys or blueprint.source_companies)
    report: dict[str, dict[str, list[str]]] = {}
    for key in keys:
        path = _filing_path(key)
        text = html_to_text(path.read_text(encoding="utf-8", errors="replace"))
        found: list[str] = []
        missing: list[str] = []
        for section in blueprint.required_sections():
            if _section_present(text, section):
                found.append(section.id)
            else:
                missing.append(section.id)
        report[key] = {"found": found, "missing": missing}
    return report
