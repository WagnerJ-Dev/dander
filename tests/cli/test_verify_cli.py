"""CLI contract for deployment verification evidence."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from dander.bootstrap import DeploymentSummary, VerificationCheck
from dander.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_verify_deployment_writes_summary_and_returns_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    summary = DeploymentSummary(
        project_id="proof-project",
        checked_at_utc="2026-07-30T00:00:00Z",
        checks=(VerificationCheck("project", True, "active"),),
    )

    class FakeVerifier:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def verify(self, **_kwargs: object) -> DeploymentSummary:
            return summary

    monkeypatch.setattr("dander.cli.main.DeploymentVerifier", FakeVerifier)
    output = tmp_path / "evidence.json"
    result = CliRunner().invoke(
        app,
        ["verify", "deployment", "--project", "proof-project", "--json", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True


def test_verify_deployment_fails_when_a_check_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    summary = DeploymentSummary(
        project_id="proof-project",
        checked_at_utc="2026-07-30T00:00:00Z",
        checks=(VerificationCheck("remote_state", False, "unavailable"),),
    )

    class FakeVerifier:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def verify(self, **_kwargs: object) -> DeploymentSummary:
            return summary

    monkeypatch.setattr("dander.cli.main.DeploymentVerifier", FakeVerifier)
    result = CliRunner().invoke(
        app,
        [
            "verify",
            "deployment",
            "--project",
            "proof-project",
            "--json",
            str(tmp_path / "evidence.json"),
        ],
    )

    assert result.exit_code == 1
    assert result.exception is not None
    assert "verification failed" in str(result.exception)
