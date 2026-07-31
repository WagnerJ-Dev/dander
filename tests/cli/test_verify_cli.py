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
    evidence_dir = tmp_path / "bundle"
    result = CliRunner().invoke(
        app,
        [
            "verify",
            "deployment",
            "--project",
            "proof-project",
            "--state-bucket",
            "proof-state",
            "--state-prefix",
            "dander/state",
            "--json",
            str(output),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True
    assert (evidence_dir / "manifest.json").exists()
    assert (evidence_dir / "bootstrap.json").exists()


def test_verify_deployment_retains_cost_guard_proof(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    summary = DeploymentSummary(
        project_id="proof-project",
        checked_at_utc="2026-07-30T00:00:00Z",
        checks=(
            VerificationCheck("project", True, "active"),
            VerificationCheck("cost_guard:budget", True, "verified"),
            VerificationCheck("cost_guard:function", True, "verified"),
        ),
    )

    class FakeVerifier:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def verify(self, **_kwargs: object) -> DeploymentSummary:
            return summary

    monkeypatch.setattr("dander.cli.main.DeploymentVerifier", FakeVerifier)
    evidence_dir = tmp_path / "bundle"
    result = CliRunner().invoke(
        app,
        [
            "verify",
            "deployment",
            "--project",
            "proof-project",
            "--state-bucket",
            "proof-state",
            "--state-prefix",
            "dander/state",
            "--json",
            str(tmp_path / "evidence.json"),
            "--evidence-dir",
            str(evidence_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    cost_guard = json.loads((evidence_dir / "cost-guard.json").read_text(encoding="utf-8"))
    assert cost_guard["status"] == "passed"


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
            "--state-bucket",
            "proof-state",
            "--state-prefix",
            "dander/state",
            "--json",
            str(tmp_path / "evidence.json"),
        ],
    )

    assert result.exit_code == 1
    assert result.exception is not None
    assert "verification failed" in str(result.exception)
