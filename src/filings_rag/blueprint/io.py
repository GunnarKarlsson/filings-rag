"""Load / save blueprint YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from filings_rag.blueprint.model import Blueprint, SectionSpec


def load_blueprint(path: Path) -> Blueprint:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    sections = tuple(
        SectionSpec(
            id=s["id"],
            item=str(s["item"]),
            title=s["title"],
            required=bool(s["required"]),
            header_patterns=tuple(s.get("header_patterns") or []),
            aliases_seen=tuple(s.get("aliases_seen") or []),
            parent=s.get("parent"),
            compact_needles=tuple(s.get("compact_needles") or []),
            content=s.get("content"),
        )
        for s in raw["sections"]
    )
    return Blueprint(
        source_companies=tuple(raw.get("source_companies") or []),
        notes=str(raw.get("notes") or ""),
        sections=sections,
    )


def save_blueprint(blueprint: Blueprint, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_companies": list(blueprint.source_companies),
        "notes": blueprint.notes,
        "sections": [
            {
                "id": s.id,
                "item": s.item,
                "title": s.title,
                "required": s.required,
                "parent": s.parent,
                "content": s.content,
                "header_patterns": list(s.header_patterns),
                "compact_needles": list(s.compact_needles),
                "aliases_seen": list(s.aliases_seen),
            }
            for s in blueprint.sections
        ],
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
