"""Stage-zero administrative bootstrap tests."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from dander.bootstrap import AdministrativeBootstrap, AdministrativeBootstrapError

if TYPE_CHECKING:
    from pathlib import Path


def test_admin_bootstrap_plans_and_applies_saved_plan(
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
    plan = AdministrativeBootstrap(tmp_path).execute(
        project="unit-project",
        state_bucket="unit-state-bucket",
        admin_member="user:operator@example.invalid",
        apply=True,
        billing_account_id="ABCDEF-123456-ABCDEF",
    )

    assert plan == tmp_path.resolve() / "dander-admin-bootstrap.tfplan"
    assert commands[0] == (
        "terraform",
        "init",
        "-reconfigure",
        "-input=false",
        "-backend-config=bucket=unit-state-bucket",
        "-backend-config=prefix=dander/bootstrap-admin/state",
    )
    assert not any("credentials" in argument for argument in commands[0])
    assert "-var=state_bucket=unit-state-bucket" in commands[1]
    assert "-var=admin_member=user:operator@example.invalid" in commands[1]
    assert commands[2] == ("terraform", "apply", "dander-admin-bootstrap.tfplan")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"state_bucket": "bad bucket"}, "state bucket"),
        ({"admin_member": "operator@example.invalid"}, "admin member"),
        ({"billing_account_id": "not-a-billing-account"}, "Billing account"),
    ],
)
def test_admin_bootstrap_rejects_unsafe_inputs(
    tmp_path: Path,
    overrides: dict[str, str],
    message: str,
) -> None:
    arguments = {
        "project": "unit-project",
        "state_bucket": "unit-state-bucket",
        "admin_member": "user:operator@example.invalid",
        "apply": False,
        **overrides,
    }

    with pytest.raises(AdministrativeBootstrapError, match=message):
        AdministrativeBootstrap(tmp_path).execute(**arguments)  # type: ignore[arg-type]
