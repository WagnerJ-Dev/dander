"""Terraform bootstrap tests for DANDER-20."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from dander.bootstrap import TerraformBootstrap

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_bootstrap_plans_without_applying(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[tuple[str, ...]] = []

    def fake_run(
        args: tuple[str, ...],
        *,
        cwd: Path,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd == tmp_path.resolve()
        assert check
        commands.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    plan = TerraformBootstrap(tmp_path).execute(
        project="unit-project",
        state_bucket="unit-state",
        state_prefix="dander/state",
        apply=False,
    )

    assert plan == tmp_path.resolve() / "dander-bootstrap.tfplan"
    assert commands[0][:2] == ("terraform", "init")
    assert commands[1][:2] == ("terraform", "plan")
    assert all(command[:2] != ("terraform", "apply") for command in commands)
