"""CLI coverage for transform build and test command wiring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from dander.cli.main import app
from dander.transform import TransformRunResult

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


class _FakeRunner:
    calls: list[tuple[str, Path, tuple[str, ...] | None]] = []

    def __init__(self, *, project: str) -> None:
        assert project == "valid-project-123"

    def build(
        self,
        models_dir: Path,
        *,
        selected: list[str] | None = None,
    ) -> TransformRunResult:
        self.calls.append(("build", models_dir, tuple(selected) if selected else None))
        return TransformRunResult(models=("selected_model",), assertions=2)

    def test(
        self,
        models_dir: Path,
        *,
        selected: list[str] | None = None,
    ) -> TransformRunResult:
        self.calls.append(("test", models_dir, tuple(selected) if selected else None))
        return TransformRunResult(models=("selected_model",), assertions=2)


def test_build_command_wires_selection_and_prints_summary(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    _FakeRunner.calls.clear()
    monkeypatch.setattr("dander.cli.main.BigQueryTransformRunner", _FakeRunner)

    result = CliRunner().invoke(
        app,
        [
            "build",
            "--project",
            "valid-project-123",
            "--models-dir",
            str(tmp_path),
            "--select",
            "selected_model",
        ],
    )

    assert result.exit_code == 0
    assert _FakeRunner.calls == [("build", tmp_path, ("selected_model",))]
    assert "Built 1 model(s); 2 assertion(s) passed." in result.stdout


def test_test_command_uses_test_only_path(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    _FakeRunner.calls.clear()
    monkeypatch.setattr("dander.cli.main.BigQueryTransformRunner", _FakeRunner)

    result = CliRunner().invoke(
        app,
        [
            "test",
            "--project",
            "valid-project-123",
            "--models-dir",
            str(tmp_path),
            "--select",
            "selected_model",
        ],
    )

    assert result.exit_code == 0
    assert _FakeRunner.calls == [("test", tmp_path, ("selected_model",))]
    assert "Tested 1 model(s); 2 assertion(s) passed." in result.stdout
