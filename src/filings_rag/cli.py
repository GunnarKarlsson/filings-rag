"""CLI entrypoint (Typer)."""

from pathlib import Path

import typer

from filings_rag import __version__
from filings_rag.blueprint import build_blueprint, coverage_report, save_blueprint
from filings_rag.config import BLUEPRINT_PATH, FILINGS_10K_DIR, PROJECT_ROOT

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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
