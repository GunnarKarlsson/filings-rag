# Filings-RAG

Local Q&A over real SEC **10-K** HTML filings. The long-term shape is RAG (chunk → embed → retrieve) with answers from a Chat Completions API. Right now the repo has the **local filing corpus** and a small **CLI skeleton**.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Python 3.12 (see `.python-version`)

## Get the 10-K corpus

Company names and primary 10-K URLs are listed in [`companies/initial_company_list.txt`](companies/initial_company_list.txt). Download once into `data/10k/` (the app only reads local files after that — not a scraper product):

```bash
./scripts/download_10k.sh
```

Layout:

```text
data/10k/{company_key}/{accession}/10k.htm
data/10k/{company_key}/{accession}/meta.json
```

See [`data/NOTICE`](data/NOTICE) for SEC/EDGAR notes. Tests use this real HTML (no synthetic fixtures).

## Setup

```bash
uv sync
uv run filings-rag --help
uv run filings-rag status
uv run pytest -q
```

`filings-rag status` reports whether the corpus is present and which company keys were found.

## Stack versions

Prefer `uv.lock` as the install source of truth.

| Component | Version | Notes |
| --- | --- | --- |
| Python | 3.12.13 | `.python-version` = `3.12` |
| uv | 0.13.10 | Astral installer |
| typer | 0.29.2 | CLI |
| pytest | 9.2.0 | Dev dependency group |

## What’s next

Ingest (parse/chunk), local embeddings + vector search, then grounded `ask` with citations.
