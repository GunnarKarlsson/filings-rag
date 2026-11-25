"""CLI entrypoint (Typer). Step 2: --help and status stub only."""

from pathlib import Path

import typer

from filings_rag import __version__
from filings_rag.config import FILINGS_10K_DIR, PROJECT_ROOT

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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
