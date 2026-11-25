"""HTML table helpers and statement fingerprints for hotspot selection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import Tag

from filings_rag.parse.model import TableBlock

# Reject MD&A ratio / YoY bridge tables that share statement titles.
_REJECT_PERCENT = re.compile(r"(?i)\bpercent change\b")
_REJECT_CASH_FLOW_BLOCK = re.compile(
    r"(?i)(cash flows? from operating|investing activities|financing activities)"
)
_REJECT_DEFERRED = re.compile(r"(?i)deferred revenues?, current")


@dataclass(frozen=True)
class TableFingerprint:
    """Content checks that identify the real statement table among candidates."""

    require_all: tuple[re.Pattern[str], ...]
    reject_any: tuple[re.Pattern[str], ...] = ()


# Fingerprints are parse rules, not company anecdotes.
FINGERPRINTS: dict[str, TableFingerprint] = {
    "fs_income": TableFingerprint(
        require_all=(
            re.compile(r"(?i)\b(revenues?|net (product )?sales|total revenues?)\b"),
            re.compile(
                r"(?i)\b(cost of|operating expenses|gross (profit|margin)|"
                r"research and development|net (income|earnings))\b"
            ),
        ),
        reject_any=(
            _REJECT_PERCENT,
            _REJECT_CASH_FLOW_BLOCK,
            _REJECT_DEFERRED,
        ),
    ),
    "fs_comprehensive_income": TableFingerprint(
        require_all=(
            re.compile(r"(?i)\b(comprehensive income|other comprehensive)\b"),
            re.compile(r"(?i)\b(net (income|earnings)|total comprehensive)\b"),
        ),
        reject_any=(_REJECT_PERCENT, _REJECT_CASH_FLOW_BLOCK),
    ),
    "fs_balance_sheet": TableFingerprint(
        require_all=(
            re.compile(r"(?i)\btotal assets\b"),
            re.compile(
                r"(?i)\b(total liabilities|stockholders['’]? equity|"
                r"shareholders['’]? equity)\b"
            ),
        ),
        reject_any=(_REJECT_PERCENT,),
    ),
    "fs_equity": TableFingerprint(
        require_all=(
            re.compile(
                r"(?i)\b(common stock|additional paid[- ]in capital|"
                r"retained earnings|treasury stock)\b"
            ),
            re.compile(
                r"(?i)\b(stockholders|shareholders|total equity|balances)\b"
            ),
        ),
        reject_any=(_REJECT_PERCENT, _REJECT_CASH_FLOW_BLOCK),
    ),
    "fs_cash_flows": TableFingerprint(
        require_all=(
            re.compile(
                r"(?i)\b(cash flows? from operating|operating activities|"
                r"net cash (provided|used))\b"
            ),
            re.compile(r"(?i)\b(investing|financing)\b"),
        ),
        reject_any=(_REJECT_PERCENT,),
    ),
    "fs_schedule_ii": TableFingerprint(
        require_all=(
            re.compile(r"(?i)\b(valuation|allowance|qualifying accounts)\b"),
            re.compile(r"(?i)\b(balance|additions|deductions|charged)\b"),
        ),
    ),
}


def table_to_block(table: Tag, *, max_rows: int = 200) -> TableBlock:
    rows: list[tuple[str, ...]] = []
    for tr in table.find_all("tr"):
        cells = [
            " ".join(c.get_text(" ", strip=True).split())
            for c in tr.find_all(["td", "th"])
        ]
        cells = [c for c in cells if c]
        if cells:
            rows.append(tuple(cells))
        if len(rows) >= max_rows:
            break
    return TableBlock(rows=tuple(rows))


def table_blob(block: TableBlock, *, head_rows: int | None = None) -> str:
    rows = block.rows if head_rows is None else block.rows[:head_rows]
    return " ".join(" ".join(row) for row in rows)


def score_table(block: TableBlock, fingerprint: TableFingerprint) -> int:
    """Higher is better. Negative means reject."""
    if len(block.rows) < 4:
        return -1
    head = table_blob(block, head_rows=6)
    blob = table_blob(block)
    for pat in fingerprint.reject_any:
        # Percent-change check only on the table head (MD&A bridges).
        if pat is _REJECT_PERCENT and pat.search(head):
            return -1
        if pat is not _REJECT_PERCENT and pat.search(blob):
            return -1
    for pat in fingerprint.require_all:
        if not pat.search(blob):
            return -1
    nums = len(re.findall(r"[\d,]{3,}", blob))
    return nums + len(block.rows)


def format_rows(rows: tuple[tuple[str, ...], ...], *, max_cells: int = 8) -> str:
    lines: list[str] = []
    for row in rows:
        cells = list(row[:max_cells])
        if len(row) > max_cells:
            cells.append("…")
        lines.append(" | ".join(cells))
    return "\n".join(lines)
