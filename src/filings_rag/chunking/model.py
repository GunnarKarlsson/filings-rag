"""Chunk records produced from parsed sections."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """One retrieval unit cut from a parsed section."""

    chunk_id: str
    company_key: str
    accession_number: str
    cik: str
    company_name: str
    form: str
    fiscal_year: int | None
    sec_url: str
    section_id: str
    item: str
    chunk_index: int
    start_offset: int
    end_offset: int
    text: str
    content_hash: str
