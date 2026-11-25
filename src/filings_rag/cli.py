"""CLI entrypoint (Typer)."""

from pathlib import Path

import typer

from filings_rag import __version__
from filings_rag.blueprint import build_blueprint, coverage_report, save_blueprint
from filings_rag.blueprint.io import load_blueprint
from filings_rag.config import BLUEPRINT_PATH, FILINGS_10K_DIR, PROJECT_ROOT
from filings_rag.parse import format_rows, list_filing_paths, parse_filing

app = typer.Typer(
    name="filings-rag",
    help="Ask questions over local SEC 10-K filings (RAG + Chat Completions).",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Ask questions over local SEC 10-K filings (RAG + Chat Completions)."""


@app.command()
def status() -> None:
    """Show package version and whether the local 10-K corpus is present."""
    filings = (
        sorted(FILINGS_10K_DIR.glob("*/*/10k.htm")) if FILINGS_10K_DIR.is_dir() else []
    )

    typer.echo(f"filings-rag {__version__}")
    typer.echo(f"project_root: {PROJECT_ROOT}")
    typer.echo(f"filings_dir:  {FILINGS_10K_DIR}")
    if not filings:
        typer.echo("10-K corpus:  missing (run ./scripts/download_10k.sh)")
        raise typer.Exit(code=1)

    companies = sorted({Path(p).parts[-3] for p in filings})
    typer.echo(f"10-K corpus:  {len(filings)} filing(s), {len(companies)} company key(s)")
    typer.echo(f"companies:    {', '.join(companies)}")


@app.command()
def blueprint(
    companies: str = typer.Option(
        "nvidia,apple,microsoft",
        "--companies",
        help="Comma-separated company keys under data/10k/ used as evidence.",
    ),
    output: Path = typer.Option(
        BLUEPRINT_PATH,
        "--output",
        help="Where to write 10k_sections.yaml",
    ),
) -> None:
    """Build a 10-K section blueprint from real local filings and check coverage."""
    keys = [k.strip() for k in companies.split(",") if k.strip()]
    if len(keys) < 2:
        typer.echo("Need at least two company keys for a useful blueprint.", err=True)
        raise typer.Exit(code=1)

    bp = build_blueprint(keys)
    save_blueprint(bp, output)
    typer.echo(f"Wrote {output}")
    typer.echo(f"sections: {len(bp.sections)} ({len(bp.required_sections())} required)")

    report = coverage_report(bp, keys)
    missing_any = False
    for company, result in report.items():
        if result["missing"]:
            missing_any = True
            typer.echo(
                f"coverage {company}: MISSING {', '.join(result['missing'])}",
                err=True,
            )
        else:
            typer.echo(
                f"coverage {company}: ok ({len(result['found'])} required headers found)"
            )

    if missing_any:
        raise typer.Exit(code=1)


@app.command("parse")
def parse_cmd(
    company: str | None = typer.Option(
        None,
        "--company",
        help="Company key under data/10k/ (default: every local filing).",
    ),
    section: str = typer.Option(
        "fs_income",
        "--section",
        help="Which cut-out to show, by checklist id (fs_income, fs_balance_sheet, item_1a, …).",
    ),
    rows: int = typer.Option(
        10,
        "--rows",
        help="For statement tables, how many rows to print.",
    ),
    blueprint_path: Path = typer.Option(
        BLUEPRINT_PATH,
        "--blueprint",
        help="Checklist YAML (default: data/blueprint/10k_sections.yaml).",
    ),
) -> None:
    """Cut sections out of local 10-K HTML using the blueprint checklist; print one of them."""
    if not blueprint_path.is_file():
        typer.echo(f"Missing blueprint: {blueprint_path}", err=True)
        raise typer.Exit(code=1)

    blueprint = load_blueprint(blueprint_path)
    paths = list_filing_paths(FILINGS_10K_DIR)
    if company:
        paths = [p for p in paths if p.parts[-3] == company]
        if not paths:
            typer.echo(f"No filing for company key {company!r}", err=True)
            raise typer.Exit(code=1)

    if not paths:
        typer.echo("No local 10-K HTML under data/10k/", err=True)
        raise typer.Exit(code=1)

    for path in paths:
        parsed = parse_filing(path, blueprint)
        typer.echo(f"\n{parsed.company_key}  sections={len(parsed.sections)}  {path}")
        extracted = parsed.get(section)
        if extracted is None:
            typer.echo(f"  missing section {section!r}", err=True)
            raise typer.Exit(code=1)
        table = extracted.primary_table()
        if table is not None:
            typer.echo(f"  {section}: {len(table.rows)} table rows (showing {rows})")
            typer.echo(format_rows(table.preview_rows(rows)))
        else:
            preview = extracted.text[:1_200].replace("\n", " ")
            typer.echo(f"  {section}: {len(extracted.text)} chars")
            typer.echo(f"  {preview}…")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
