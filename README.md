# Filings-RAG

Local Q&A over real SEC **10-K** HTML filings. The long-term shape is RAG (chunk → embed → retrieve) with answers from a Chat Completions API. Right now the repo has the **local filing corpus**, a **section blueprint** derived from real 10-Ks, and a small **CLI**.

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

## Section blueprint

Inspect a few real filings and write the canonical Item list (with aliases and required/optional flags) used later for parse coverage:

```bash
uv run filings-rag blueprint --companies nvidia,apple,microsoft
```

Output: [`data/blueprint/10k_sections.yaml`](data/blueprint/10k_sections.yaml).

Form 10-K **ITEM** numbers are fixed by the SEC. The blueprint lists those ITEMs plus financial-statement **lookup hotspots**: auditor report, income/operations, comprehensive income, balance sheet, equity, cash flows, notes (**Item 8**), and Schedule II when present (**Item 15**).

**Parse rules:** match ITEM headings and statement titles with the patterns in the YAML. Primary statements satisfy Item 8; Item 15(a)(1) is an index. If an index/TOC entry is a `#fragment` link, resolve it and extract the linked body (usually the HTML table)—not TOC page numbers. Do not assume tables sit at one fixed place under an ITEM heading.

## Stack versions

Prefer `uv.lock` as the install source of truth.

| Component | Version | Notes |
| --- | --- | --- |
| Python | 3.12.13 | `.python-version` = `3.12` |
| uv | 0.13.10 | Astral installer |
| typer | 0.29.2 | CLI |
| beautifulsoup4 | 4.15.0 | HTML → text for header detection |
| PyYAML | 6.0.4 | Blueprint file |
| pytest | 9.2.0 | Dev dependency group |

## What’s next

Parse HTML into blueprint sections, then chunk/embed/retrieve and grounded `ask` with citations.
