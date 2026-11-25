"""Detect ITEM headers and named financial-statement sections in 10-K HTML."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

# Section-like: "ITEM 1A. Risk Factors" / "Item 7. Management's Discussion..."
_HEADER = re.compile(
    r"(?i)\bITEM\s+(\d{1,2}[A-C]?)\s*[.\u00a0\s]+\s*([A-Z\[].{2,120}?)"
    r"(?=(?:\n|$|[.]{2,}|\s{2,}Item\s+\d))",
)

# Cross-references and narrative mentions — not section starts.
_SKIP_TITLE = re.compile(
    r"(?i)^(of this|for (a |further )?discussion|under the heading|see |in our|"
    r"and related|which information|for additional|for further|describes |"
    r"beginning |readers are|as a result)"
)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def compact_text(text: str) -> str:
    """Lowercase alphanumerics only (handles tag-split words and curly quotes)."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def detect_item_headers(html: str) -> dict[str, str]:
    """
    Return map of item number -> best title string found in the filing text.
    Keys look like "1", "1A", "7A".
    """
    text = html_to_text(html)
    found: dict[str, str] = {}

    for match in _HEADER.finditer(text):
        item = match.group(1).upper()
        title = match.group(2).strip()
        title = re.sub(r"\s+", " ", title)
        title = title.strip(" .;:,")
        title = re.split(r"&#|\s+Item\s+\d", title, maxsplit=1)[0].strip(" .")
        if len(title) < 3:
            continue
        if _SKIP_TITLE.search(title):
            continue
        if title.upper().startswith("ITEM "):
            continue

        def _quality(t: str) -> tuple[int, int]:
            mixed = 1 if any(c.islower() for c in t) else 0
            return (mixed, len(t))

        prev = found.get(item)
        if prev is None or _quality(title) > _quality(prev):
            found[item] = title[:120]

    return found


def detect_item_headers_in_file(path: Path) -> dict[str, str]:
    html = path.read_text(encoding="utf-8", errors="replace")
    return detect_item_headers(html)


def item_mentioned_in_text(text: str, item: str) -> bool:
    """True if a section-style ITEM header for this number appears in plain text."""
    pattern = re.compile(
        rf"(?i)\bITEM\s+{re.escape(item)}\s*[.\u00a0\s]+[A-Z\[]",
    )
    for match in pattern.finditer(text):
        window = text[match.start() : match.start() + 60]
        if re.search(r"(?i)of this (Form|Annual Report)", window):
            continue
        return True
    return False


def item_mentioned(html: str, item: str) -> bool:
    return item_mentioned_in_text(html_to_text(html), item)


def named_section_in_text(
    text: str,
    *,
    header_patterns: tuple[str, ...],
    compact_needles: tuple[str, ...] = (),
) -> bool:
    """True if a named subsection header appears (regex and/or compact needle)."""
    for pattern in header_patterns:
        if re.search(pattern, text):
            return True
    if compact_needles:
        blob = compact_text(text)
        for needle in compact_needles:
            if needle.lower() in blob:
                return True
    return False


def find_named_aliases(text: str, patterns: tuple[str, ...]) -> tuple[str, ...]:
    """Collect short matched snippets as aliases_seen evidence."""
    aliases: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            snippet = re.sub(r"\s+", " ", match.group(0)).strip()
            # Drop trailing "for the years ended..." clutter from TOC lines
            snippet = re.split(
                r"(?i)\s+for the years?\s+ended|\s+as of\s+",
                snippet,
                maxsplit=1,
            )[0].strip(" .")
            if snippet and snippet not in aliases:
                aliases.append(snippet[:120])
            if len(aliases) >= 4:
                return tuple(aliases)
    return tuple(aliases)
