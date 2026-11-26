"""Build chunks from a parsed filing + filing metadata."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from filings_rag.blueprint.model import Blueprint
from filings_rag.chunking.model import Chunk
from filings_rag.chunking.split import (
    DEFAULT_CHUNK_CHARS,
    DEFAULT_OVERLAP_CHARS,
    split_text,
)
from filings_rag.parse.model import ExtractedSection, ParsedFiling
from filings_rag.parse.tables import format_rows


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_filing_meta(htm_path: Path) -> dict[str, str]:
    meta_path = htm_path.parent / "meta.json"
    if not meta_path.is_file():
        return {}
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in raw.items()}


def company_display_name(company_key: str) -> str:
    """Human-readable label from the folder key (e.g. google_alphabet → Google Alphabet)."""
    return company_key.replace("_", " ").title()


def _fiscal_year_from_meta(meta: dict[str, str], htm_path: Path) -> int | None:
    primary = meta.get("primary_document", htm_path.name)
    # e.g. nvda-20260125.htm → period end 2026-01-25 → fiscal year often year of period end
    match = re.search(r"(20\d{2})\d{4}", primary)
    if match:
        return int(match.group(1))
    return None


def _section_text(section: ExtractedSection) -> str:
    table = section.primary_table()
    if table is not None and table.rows:
        header = f"{section.title}\n"
        return header + format_rows(table.rows, max_cells=12)
    return section.text.strip()


def _item_for_section(section: ExtractedSection, blueprint: Blueprint) -> str:
    spec = blueprint.by_id().get(section.section_id)
    if spec is not None:
        return spec.item
    if section.section_id.startswith("item_"):
        return section.section_id.removeprefix("item_").upper()
    return "8"


def chunks_for_filing(
    parsed: ParsedFiling,
    blueprint: Blueprint,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    meta = load_filing_meta(parsed.path)
    company_key = parsed.company_key
    accession = meta.get("accession") or parsed.path.parent.name
    cik = meta.get("cik", "")
    sec_url = meta.get("sec_url", "")
    company_name = company_display_name(company_key)
    fiscal_year = _fiscal_year_from_meta(meta, parsed.path)

    out: list[Chunk] = []
    for section in parsed.sections:
        body = _section_text(section)
        if not body:
            continue
        item = _item_for_section(section, blueprint)
        windows = split_text(
            body, chunk_chars=chunk_chars, overlap_chars=overlap_chars
        )
        for index, (start, end, piece) in enumerate(windows):
            content_hash = _sha256(piece)
            chunk_id = _sha256(
                f"{company_key}|{accession}|{section.section_id}|{index}|{content_hash}"
            )
            out.append(
                Chunk(
                    chunk_id=chunk_id,
                    company_key=company_key,
                    accession_number=accession,
                    cik=cik,
                    company_name=company_name,
                    form="10-K",
                    fiscal_year=fiscal_year,
                    sec_url=sec_url,
                    section_id=section.section_id,
                    item=item,
                    chunk_index=index,
                    start_offset=start,
                    end_offset=end,
                    text=piece,
                    content_hash=content_hash,
                )
            )
    return out
