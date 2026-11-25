"""Minimal smoke tests for the package skeleton (Step 2)."""

from typer.testing import CliRunner

from filings_rag import __version__
from filings_rag.cli import app
from filings_rag.config import FILINGS_10K_DIR, PROJECT_ROOT


def test_version_string() -> None:
    assert __version__


def test_filings_dir_is_under_project_data() -> None:
    assert FILINGS_10K_DIR == PROJECT_ROOT / "data" / "10k"


def test_cli_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "filings-rag" in result.stdout


def test_cli_status_sees_local_corpus() -> None:
    result = CliRunner().invoke(app, ["status"])
    assert result.exit_code == 0, result.stdout
    assert "filing" in result.stdout.lower()
