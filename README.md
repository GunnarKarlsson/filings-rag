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
