# Filings-RAG

Ask questions over real SEC **10-K** HTML filings (local RAG + Chat Completions for answers).

## Local corpus (Step 1)

Company URLs live in [`companies/initial_company_list.txt`](companies/initial_company_list.txt). A one-shot script downloads them into `data/10k/` — after that, the app only reads local files (not a scraper product).

```bash
./scripts/download_10k.sh
```

Layout:

```text
data/10k/{company_key}/{accession}/10k.htm
data/10k/{company_key}/{accession}/meta.json
```

See [`data/NOTICE`](data/NOTICE) for SEC/EDGAR notes. Tests and later ingest steps use this real HTML (no synthetic fixtures).

## Setup (Step 2)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
uv sync
uv run filings-rag --help
uv run filings-rag status
uv run pytest -q
```

Prefer `uv.lock` as the install source of truth. Record exact pins when each step lands.

### Stack versions

| Component | Version | Introduced in step | Notes |
| --- | --- | --- | --- |
| Python | 3.12.13 | 2 | `.python-version` = `3.12`; verified via `uv run python --version` |
| uv | 0.13.10 | 2 | Astral installer |
| typer | 0.29.2 | 2 | CLI |
| pytest | 9.2.0 | 2 | Dev dependency group |

### Why we chose (filled as later steps land)

**Embedding model / Qdrant / chat model** — documented in the design plan; pins land in Steps 6 and 8.
