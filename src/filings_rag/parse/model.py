"""Parsed filing sections extracted against the blueprint."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TableBlock:
    """One HTML table as ordered rows of cell text."""

    rows: tuple[tuple[str, ...], ...]

    def preview_rows(self, n: int = 10) -> tuple[tuple[str, ...], ...]:
        return self.rows[:n]


@dataclass(frozen=True)
class ExtractedSection:
    section_id: str
    title: str
    # Plain text for narrative sections; for tables, a readable join of rows.
    text: str
    tables: tuple[TableBlock, ...] = ()

    def primary_table(self) -> TableBlock | None:
        return self.tables[0] if self.tables else None


@dataclass(frozen=True)
class ParsedFiling:
    company_key: str
    path: Path
    sections: tuple[ExtractedSection, ...]

    def by_id(self) -> dict[str, ExtractedSection]:
        return {s.section_id: s for s in self.sections}

    def get(self, section_id: str) -> ExtractedSection | None:
        return self.by_id().get(section_id)
