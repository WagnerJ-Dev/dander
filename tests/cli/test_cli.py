"""CLI behavior tests for DANDER-20."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from dander.cli.main import app

_REPO_ROOT = Path(__file__).parents[2]


def test_greenhouse_dry_run_needs_no_credentials_or_gcp() -> None:
    result = CliRunner().invoke(
        app,
        [
            "run",
            "greenhouse",
            "--dry-run",
            "--project",
            "unit-project",
            "--connectors-dir",
            str(_REPO_ROOT / "connectors"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "greenhouse_candidates" in result.output
    assert "greenhouse_jobs" in result.output
    assert "SCD1" in result.output


def test_sandbox_dry_run_declares_replace_mode_without_network() -> None:
    result = CliRunner().invoke(
        app,
        [
            "run",
            "greenhouse",
            "--sandbox",
            "--dry-run",
            "--project",
            "unit-project",
            "--connectors-dir",
            str(_REPO_ROOT / "connectors"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "REPLACE (sandbox)" in result.output
