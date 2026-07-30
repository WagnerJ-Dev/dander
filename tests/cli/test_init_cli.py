"""CLI coverage for the complete optional bootstrap."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from dander.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_init_passes_optional_runtime_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_execute(self: object, **kwargs: object) -> Path:
        captured.update(kwargs)
        return tmp_path / "dander-bootstrap.tfplan"

    monkeypatch.setattr("dander.cli.main.TerraformBootstrap.execute", fake_execute)

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--project",
            "unit-project",
            "--state-bucket",
            "unit-state",
            "--enable-runtime",
            "--billing-account",
            "ABCDEF-123456-ABCDEF",
            "--container-image",
            f"example.invalid/project/repository/image@sha256:{'a' * 64}",
            "--scheduler-enabled",
            "--secret-id",
            "api-token",
            "--github-repository",
            "WagnerJ-Dev/dander",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["enable_runtime"] is True
    assert captured["scheduler_paused"] is False
    assert captured["secret_ids"] == ("api-token",)
    assert captured["github_repository"] == "WagnerJ-Dev/dander"


def test_init_apply_requires_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    called = False

    def fake_execute(self: object, **kwargs: object) -> Path:
        nonlocal called
        called = True
        return tmp_path / "must-not-execute.tfplan"

    monkeypatch.setattr("dander.cli.main.TerraformBootstrap.execute", fake_execute)

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--project",
            "unit-project",
            "--state-bucket",
            "unit-state",
            "--apply",
        ],
        input="n\n",
    )

    assert result.exit_code != 0
    assert not called
