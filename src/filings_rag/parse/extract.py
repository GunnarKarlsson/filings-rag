"""Cut Item text and financial statement tables out of a local 10-K HTML filing."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

from filings_rag.blueprint.detect import compact_text, html_to_text
from filings_rag.blueprint.model import Blueprint, SectionSpec
from filings_rag.parse.model import ExtractedSection, ParsedFiling, TableBlock
from filings_rag.parse.tables import (
    FINGERPRINTS,
    format_rows,
    score_table,
    table_to_block,
)


def _company_key_from_path(path: Path) -> str:
    # data/10k/{company}/{accession}/10k.htm
    return path.parent.parent.name


def _compile_patterns(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in patterns)


def _text_matches_patterns(
    text: str,
    patterns: tuple[re.Pattern[str], ...],
    compact_needles: tuple[str, ...],
) -> bool:
    for pat in patterns:
        if pat.search(text):
            return True
    if compact_needles:
        blob = compact_text(text)
        for needle in compact_needles:
            if needle.lower() in blob:
                return True
    return False


def _item_heading_positions(text: str, item: str) -> list[int]:
    """Byte offsets of section-style ITEM headings (not 'see Item N of this Form')."""
    pat = re.compile(
        rf"(?i)\bITEM\s+{re.escape(item)}\s*[.\u00a0\s]+[A-Z\[]",
    )
    starts: list[int] = []
    for match in pat.finditer(text):
        window = text[match.start() : match.start() + 80]
        if re.search(r"(?i)of this (Form|Annual Report)", window):
            continue
        starts.append(match.start())
    return starts


def _extract_item_text(text: str, item: str, next_items: list[str]) -> str:
    """
    Take the body after the last ITEM heading for `item` until the next ITEM.
    Last heading skips the front TOC entry when a body heading exists.
    """
    starts = _item_heading_positions(text, item)
    if not starts:
        return ""
    start = starts[-1]
    end = len(text)
    for other in next_items:
        for pos in _item_heading_positions(text, other):
            if pos > start:
                end = min(end, pos)
    body = text[start:end].strip()
    # Cap runaway extracts (notes can be huge; ITEM narrative still useful capped).
    if len(body) > 80_000:
        body = body[:80_000]
    return body


def _resolve_fragment(soup: BeautifulSoup, href: str) -> Tag | None:
    if "#" not in href:
        return None
    frag = href.split("#", 1)[1].strip()
    if not frag:
        return None
    return soup.find(id=frag) or soup.find(attrs={"name": frag})


def _candidate_tables_for_spec(
    soup: BeautifulSoup,
    spec: SectionSpec,
) -> list[tuple[int, TableBlock]]:
    patterns = _compile_patterns(spec.header_patterns)
    scored: list[tuple[int, TableBlock]] = []
    fingerprint = FINGERPRINTS.get(spec.id)

    def consider(table: Tag, *, boost: int = 0) -> None:
        block = table_to_block(table)
        if fingerprint is None:
            # Narrative-adjacent or unknown: keep first substantial table.
            if len(block.rows) >= 3:
                scored.append((boost + len(block.rows), block))
            return
        score = score_table(block, fingerprint)
        if score >= 0:
            scored.append((score + boost, block))

    # 1) TOC / index hyperlinks whose text matches the statement title.
    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        if not label or not _text_matches_patterns(
            label, patterns, spec.compact_needles
        ):
            continue
        target = _resolve_fragment(soup, anchor["href"])
        if target is None:
            continue
        table = target if target.name == "table" else target.find_next("table")
        if table is not None:
            consider(table, boost=15)

    # 2) Title text nodes → following table.
    for pat in patterns:
        for node in soup.find_all(string=pat):
            if not isinstance(node, NavigableString):
                continue
            parent = node.parent
            if parent is None:
                continue
            table = parent.find_next("table")
            if table is not None:
                consider(table, boost=5)

    # 3) Full-document scan when title/link paths miss (pointer layouts without links).
    if not scored and fingerprint is not None:
        for table in soup.find_all("table"):
            consider(table, boost=0)

    scored.sort(key=lambda x: -x[0])
    return scored


def _extract_table_section(
    soup: BeautifulSoup,
    spec: SectionSpec,
) -> ExtractedSection | None:
    candidates = _candidate_tables_for_spec(soup, spec)
    if not candidates:
        return None
    best = candidates[0][1]
    text = format_rows(best.rows)
    return ExtractedSection(
        section_id=spec.id,
        title=spec.title,
        text=text,
        tables=(best,),
    )


def _extract_named_narrative(
    text: str,
    soup: BeautifulSoup,
    spec: SectionSpec,
) -> ExtractedSection | None:
    """Auditor report and similar: title match → following prose (and optional table)."""
    patterns = _compile_patterns(spec.header_patterns)
    # Prefer fragment link into the report body.
    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        if not _text_matches_patterns(label, patterns, spec.compact_needles):
            continue
        target = _resolve_fragment(soup, anchor["href"])
        if target is None:
            continue
        chunk = " ".join(target.get_text(" ", strip=True).split())
        # Pull a wider window of siblings after the target.
        parts = [chunk]
        for sib in target.next_siblings:
            if isinstance(sib, Tag) and sib.name == "table":
                break
            if isinstance(sib, Tag):
                piece = " ".join(sib.get_text(" ", strip=True).split())
                if piece:
                    parts.append(piece)
            if sum(len(p) for p in parts) > 6_000:
                break
        body = " ".join(parts).strip()
        if len(body) >= 80:
            return ExtractedSection(
                section_id=spec.id,
                title=spec.title,
                text=body[:12_000],
            )

    for pat in patterns:
        match = pat.search(text)
        if not match:
            continue
        # Skip very early TOC-only hits when a later body hit exists.
        matches = list(pat.finditer(text))
        match = matches[-1]
        start = match.start()
        end = min(len(text), start + 8_000)
        # Stop at next ITEM heading if any.
        nxt = re.search(r"(?i)\bITEM\s+\d", text[start + 40 : end])
        if nxt:
            end = start + 40 + nxt.start()
        body = text[start:end].strip()
        if len(body) >= 80:
            return ExtractedSection(
                section_id=spec.id,
                title=spec.title,
                text=body,
            )
    if spec.compact_needles:
        blob = compact_text(text)
        for needle in spec.compact_needles:
            idx = blob.find(needle.lower())
            if idx >= 0:
                # Approximate: needle found — fall back to pattern-less slice is hard;
                # require pattern path above for body.
                break
    return None


def parse_filing(path: Path, blueprint: Blueprint) -> ParsedFiling:
    """Parse one 10-K HTML file into blueprint sections."""
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    text = html_to_text(html)

    top_level = [s for s in blueprint.sections if s.parent is None]
    top_items = [s.item for s in top_level]

    extracted: list[ExtractedSection] = []
    for spec in blueprint.sections:
        if spec.parent is None:
            # Next top-level items after this one in blueprint order.
            try:
                idx = top_items.index(spec.item)
            except ValueError:
                idx = -1
            following = top_items[idx + 1 :] if idx >= 0 else top_items
            body = _extract_item_text(text, spec.item, following)
            if body:
                extracted.append(
                    ExtractedSection(
                        section_id=spec.id,
                        title=spec.title,
                        text=body,
                    )
                )
            continue

        # Statement grids use content fingerprints. Notes and auditor report are
        # title-anchored narrative (notes may embed tables later in chunking).
        if spec.id in FINGERPRINTS:
            section = _extract_table_section(soup, spec)
            if section is not None:
                extracted.append(section)
            continue

        section = _extract_named_narrative(text, soup, spec)
        if section is not None:
            extracted.append(section)

    return ParsedFiling(
        company_key=_company_key_from_path(path),
        path=path,
        sections=tuple(extracted),
    )


def list_filing_paths(filings_dir: Path) -> list[Path]:
    return sorted(filings_dir.glob("*/*/10k.htm"))
