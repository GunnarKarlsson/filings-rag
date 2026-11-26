"""Fixed local paths for this project (no env overrides yet)."""

from pathlib import Path

# src/filings_rag/config.py → project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FILINGS_10K_DIR = PROJECT_ROOT / "data" / "10k"
BLUEPRINT_PATH = PROJECT_ROOT / "data" / "blueprint" / "10k_sections.yaml"
INDEXES_DIR = PROJECT_ROOT / "data" / "indexes"
CATALOG_PATH = INDEXES_DIR / "catalog.sqlite"
