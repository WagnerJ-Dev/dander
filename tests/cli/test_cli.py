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


def test_public_job_board_dry_run_needs_no_credentials() -> None:
    result = CliRunner().invoke(
        app,
        [
            "run",
            "greenhouse_job_board",
            "--dry-run",
            "--project",
            "unit-project",
            "--connectors-dir",
            str(_REPO_ROOT / "connectors"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "greenhouse_job_board_jobs" in result.output


def test_dry_run_reports_configured_writer_batch_rows() -> None:
    result = CliRunner().invoke(
        app,
        [
            "run",
            "greenhouse_job_board",
            "--dry-run",
            "--project",
            "unit-project",
            "--batch-rows",
            "2048",
            "--connectors-dir",
            str(_REPO_ROOT / "connectors"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Writer batch rows: 2048" in result.output


def test_harvest_v3_dry_run_validates_without_credentials() -> None:
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


def test_guarded_free_tier_dry_run_declares_production_mode_without_network() -> None:
    result = CliRunner().invoke(
        app,
        [
            "run",
            "greenhouse",
            "--guarded-free-tier",
            "--dry-run",
            "--project",
            "unit-project",
            "--connectors-dir",
            str(_REPO_ROOT / "connectors"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "SCD1 (guarded billing)" in result.output


def test_billing_modes_are_mutually_exclusive() -> None:
    result = CliRunner().invoke(
        app,
        [
            "run",
            "greenhouse",
            "--sandbox",
            "--guarded-free-tier",
            "--dry-run",
            "--project",
            "unit-project",
            "--connectors-dir",
            str(_REPO_ROOT / "connectors"),
        ],
    )

    assert result.exit_code == 1
    assert result.exception is not None
    assert "mutually exclusive" in str(result.exception)
