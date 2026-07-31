"""Terraform bootstrap tests for DANDER-20."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from dander.bootstrap import TerraformBootstrap, TerraformBootstrapError

if TYPE_CHECKING:
    from pathlib import Path


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


def test_bootstrap_passes_complete_runtime_as_literal_arguments(
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
        commands.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    digest = "a" * 64

    TerraformBootstrap(tmp_path).execute(
        project="unit-project",
        state_bucket="unit-state",
        state_prefix="dander/state",
        apply=True,
        region="us-east1",
        bigquery_location="US",
        enable_runtime=True,
        billing_account_id="ABCDEF-123456-ABCDEF",
        container_image=f"us-east1-docker.pkg.dev/unit-project/dander/dander@sha256:{digest}",
        scheduler_paused=False,
        runtime_publish_dataplex=True,
        secret_ids=("greenhouse-client-secret", "greenhouse-client-id"),
        github_repository="WagnerJ-Dev/dander",
        github_ref="refs/heads/main",
    )

    plan = commands[1]
    assert "-var=bootstrap_billing_account_id=ABCDEF-123456-ABCDEF" in plan
    assert "-var=enable_scheduled_job=true" in plan
    assert "-var=scheduler_paused=false" in plan
    assert "-var=runtime_publish_dataplex=true" in plan
    assert '-var=secret_ids=["greenhouse-client-id","greenhouse-client-secret"]' in plan
    assert "-var=github_repository=WagnerJ-Dev/dander" in plan
    assert "-var=enable_cost_guard=false" in plan
    assert commands[2] == ("terraform", "apply", "dander-bootstrap.tfplan")


def test_bootstrap_passes_simulation_first_cost_guard(
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
        commands.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    TerraformBootstrap(tmp_path).execute(
        project="unit-project",
        state_bucket="unit-state",
        state_prefix="dander/state",
        apply=False,
        billing_account_id="ABCDEF-123456-ABCDEF",
        enable_cost_guard=True,
        cost_guard_budget_amount="4.50",
    )

    plan = commands[1]
    assert "-var=enable_cost_guard=true" in plan
    assert "-var=cost_guard_budget_amount=4.50" in plan
    assert "-var=cost_guard_simulate=true" in plan
    assert "-var=cost_guard_source_bucket=unit-state" in plan


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"enable_runtime": True}, "billing-account"),
        (
            {
                "enable_runtime": True,
                "billing_account_id": "ABCDEF-123456-ABCDEF",
                "container_image": "example.invalid/dander:latest",
            },
            "immutable",
        ),
        ({"billing_account_id": "ABCDEF-123456-ABCDEF"}, "enable-runtime"),
        ({"secret_ids": ("bad secret",)}, "secret id"),
        ({"github_repository": "not-a-repository"}, "GitHub repository"),
        ({"github_repository": "WagnerJ-Dev/dander"}, "enable-runtime"),
        ({"runtime_publish_dataplex": True}, "enable-runtime"),
        ({"github_ref": "main"}, "GitHub ref"),
        ({"enable_cost_guard": True}, "billing-account"),
        ({"live_cost_guard": True}, "enable-cost-guard"),
        ({"cost_guard_budget_amount": "5.01"}, "no greater than"),
        ({"cost_guard_budget_amount": "NaN"}, "no greater than"),
        ({"cost_guard_budget_name": "bad\nname"}, "display-name"),
    ],
)
def test_bootstrap_rejects_unsafe_optional_inputs(
    tmp_path: Path,
    overrides: dict[str, object],
    message: str,
) -> None:
    arguments: dict[str, object] = {
        "project": "unit-project",
        "state_bucket": "unit-state",
        "state_prefix": "dander/state",
        "apply": False,
        **overrides,
    }

    with pytest.raises(TerraformBootstrapError, match=message):
        TerraformBootstrap(tmp_path).execute(**arguments)  # type: ignore[arg-type]
