"""10-K section blueprint: detect headers from real filings and check coverage."""

from filings_rag.blueprint.detect import detect_item_headers
from filings_rag.blueprint.io import load_blueprint, save_blueprint
from filings_rag.blueprint.model import Blueprint, SectionSpec
from filings_rag.blueprint.build import build_blueprint, coverage_report

__all__ = [
    "Blueprint",
    "SectionSpec",
    "build_blueprint",
    "coverage_report",
    "detect_item_headers",
    "load_blueprint",
    "save_blueprint",
]
