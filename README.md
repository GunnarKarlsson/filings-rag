# Filings-RAG

Local Q&A over real SEC **10-K** HTML filings. The long-term shape is RAG (chunk → embed → retrieve) with answers from a Chat Completions API. Right now the repo has the **local filing corpus**, a **section blueprint**, an HTML **section parser**, and a small **CLI**.

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

The blueprint is a checklist of what a 10-K should contain: each SEC Item (Item 1 Business, Item 7 MD&A, Item 8 Financial Statements, …) and the named financial statements we care about (income statement, balance sheet, cash flows, and so on). It also stores the text patterns used to find those headings.

```bash
uv run filings-rag blueprint --companies nvidia,apple,microsoft
```

Writes [`data/blueprint/10k_sections.yaml`](data/blueprint/10k_sections.yaml).

## Parse a filing

`parse` reads a company’s `10k.htm` and, using that checklist, **cuts out the actual text and tables** from the HTML. The result is the filing content that matched each checklist entry.

What it does, in order:

1. **SEC Item sections** (Item 1, Item 7, Item 8, …) — find the Item heading in the body of the filing, then take the text from there until the next Item heading.
2. **Financial statement tables** (income statement, balance sheet, cash flows, …) — find the statement by its title, or by following a table-of-contents link that jumps to that title. Then keep the HTML table that looks like the real statement (for example an income statement must show revenue/sales, and must not be a cash-flow table).

Preview one cut-out (default: income statement, first 10 rows):

```bash
uv run filings-rag parse --section fs_income --rows 10
uv run filings-rag parse --company nvidia --section fs_balance_sheet
```

`--section` is the checklist id from the YAML (`fs_income` = income / operations statement, `item_1a` = Risk Factors, …).

Tests run this over **every** filing under `data/10k/` and print the first 10 rows of the income statement, balance sheet, and cash flows so you can eyeball them:

```bash
uv run pytest -s tests/unit/test_parse.py
```

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

Chunk/embed/retrieve parsed sections and grounded `ask` with citations.
