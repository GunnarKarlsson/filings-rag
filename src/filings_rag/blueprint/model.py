"""Blueprint data shapes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionSpec:
    id: str
    item: str
    title: str
    required: bool
    header_patterns: tuple[str, ...]
    aliases_seen: tuple[str, ...] = ()
    # SEC ITEM that owns this subsection (Item 8 for primary statements;
    # Item 15 for supplemental schedules). Not the HTML position in the file.
    parent: str | None = None
    # Space-insensitive phrases for HTML that splits words across tags (e.g. Microsoft).
    compact_needles: tuple[str, ...] = ()
    # What the body target usually contains once TOC links are followed.
    # "tables" = financial statement grids are the retrieval hotspot.
    content: str | None = None


@dataclass(frozen=True)
class Blueprint:
    source_companies: tuple[str, ...]
    notes: str
    sections: tuple[SectionSpec, ...]

    def required_sections(self) -> tuple[SectionSpec, ...]:
        return tuple(s for s in self.sections if s.required)

    def by_id(self) -> dict[str, SectionSpec]:
        return {s.id: s for s in self.sections}
