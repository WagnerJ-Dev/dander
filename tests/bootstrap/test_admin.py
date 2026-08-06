"""Stage-zero administrative bootstrap tests."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

from dander.bootstrap import AdministrativeBootstrap, AdministrativeBootstrapError


def test_admin_bootstrap_plans_and_applies_saved_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository_dir = tmp_path / "checkout"
    infra_dir = repository_dir / "infra" / "bootstrap-admin"
    operator_dir = tmp_path / "operator-artifacts"
    infra_dir.mkdir(parents=True)
    commands: list[tuple[str, ...]] = []
    environments: list[dict[str, str]] = []
    umasks: list[int] = []

    def fake_run(
        args: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        umask: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd == infra_dir.resolve()
        assert check
        commands.append(args)
        environments.append(env)
        umasks.append(umask)
        for argument in args:
            if argument.startswith("-out="):
                Path(argument.removeprefix("-out=")).touch(mode=0o644)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    plan = AdministrativeBootstrap(infra_dir, operator_dir).execute(
        project="unit-project",
        state_bucket="unit-state-bucket",
        admin_member="user:operator@example.invalid",
        apply=True,
        billing_account_id="ABCDEF-123456-ABCDEF",
    )

    assert plan == operator_dir.resolve() / "dander-admin-bootstrap.tfplan"
    assert not plan.is_relative_to(repository_dir.resolve())
    tf_data_dir = Path(environments[0]["TF_DATA_DIR"])
    assert not tf_data_dir.is_relative_to(repository_dir.resolve())
    assert tf_data_dir == operator_dir / "terraform-data"
    assert stat.S_IMODE(operator_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(tf_data_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(plan.stat().st_mode) == 0o600
    assert all(environment["TF_DATA_DIR"] == str(tf_data_dir) for environment in environments)
    assert umasks == [0o077, 0o077, 0o077]
    assert commands[0] == (
        "terraform",
        "init",
        "-reconfigure",
        "-input=false",
        "-backend-config=bucket=unit-state-bucket",
        "-backend-config=prefix=dander/bootstrap-admin/state",
    )
    assert not any("credentials" in argument for command in commands for argument in command)
    assert not any("-backend=false" in argument for command in commands for argument in command)
    assert not any("-lock=false" in argument for command in commands for argument in command)
    assert not any("state_prefix" in argument for command in commands for argument in command)
    assert "-var=state_bucket=unit-state-bucket" in commands[1]
    assert "-var=admin_member=user:operator@example.invalid" in commands[1]
    assert f"-out={plan}" in commands[1]
    assert commands[2] == ("terraform", "apply", str(plan))


def test_admin_bootstrap_adopts_precreated_backend_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    infra_dir = tmp_path / "checkout" / "infra" / "bootstrap-admin"
    operator_dir = tmp_path / "operator"
    infra_dir.mkdir(parents=True)
    commands: list[tuple[str, ...]] = []

    def fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if args[:3] == ("terraform", "state", "show"):
            return subprocess.CompletedProcess(args, 1)
        for argument in args:
            if argument.startswith("-out="):
                Path(argument.removeprefix("-out=")).touch()
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    AdministrativeBootstrap(infra_dir, operator_dir).execute(
        project="unit-project",
        state_bucket="unit-state-bucket",
        admin_member="user:operator@example.invalid",
        apply=False,
        adopt_state_bucket=True,
    )

    imported = next(command for command in commands if command[:2] == ("terraform", "import"))
    assert imported[-2:] == ("google_storage_bucket.terraform_state", "unit-state-bucket")


def test_admin_apply_uses_only_the_previously_saved_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    infra_dir = tmp_path / "checkout" / "infra" / "bootstrap-admin"
    operator_dir = tmp_path / "operator"
    infra_dir.mkdir(parents=True)
    commands: list[tuple[str, ...]] = []

    def fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        for argument in args:
            if argument.startswith("-out="):
                Path(argument.removeprefix("-out=")).touch()
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    bootstrap = AdministrativeBootstrap(infra_dir, operator_dir)
    plan = bootstrap.execute(
        project="unit-project",
        state_bucket="unit-state-bucket",
        admin_member="user:operator@example.invalid",
        apply=False,
    )
    commands.clear()

    applied = bootstrap.apply_saved_plan(state_bucket="unit-state-bucket")

    assert applied == plan
    assert commands[-1] == ("terraform", "apply", str(plan))
    assert not any(command[:2] == ("terraform", "plan") for command in commands)


@pytest.mark.parametrize("artifact_name", ["terraform-data", "dander-admin-bootstrap.tfplan"])
def test_admin_bootstrap_rejects_preexisting_operator_symlinks_before_terraform(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    artifact_name: str,
) -> None:
    repository_dir = tmp_path / "checkout"
    infra_dir = repository_dir / "infra" / "bootstrap-admin"
    operator_dir = tmp_path / "operator-artifacts"
    infra_dir.mkdir(parents=True)
    operator_dir.mkdir()
    (operator_dir / artifact_name).symlink_to(tmp_path / f"target-{artifact_name}")
    calls: list[tuple[str, ...]] = []

    def fail_if_run(args: tuple[str, ...], **kwargs: object) -> None:
        calls.append(args)
        raise AssertionError("Terraform must not run for a pre-existing symlink")

    monkeypatch.setattr(subprocess, "run", fail_if_run)

    with pytest.raises(AdministrativeBootstrapError, match="symlink"):
        AdministrativeBootstrap(infra_dir, operator_dir).execute(
            project="unit-project",
            state_bucket="unit-state-bucket",
            admin_member="user:operator@example.invalid",
            apply=False,
        )

    assert calls == []


@pytest.mark.parametrize("operator_dir", [".", "artifacts"])
def test_admin_bootstrap_rejects_operator_artifacts_inside_repository(
    tmp_path: Path,
    operator_dir: str,
) -> None:
    repository_dir = tmp_path / "checkout"
    infra_dir = repository_dir / "infra" / "bootstrap-admin"

    with pytest.raises(AdministrativeBootstrapError, match="outside the repository"):
        AdministrativeBootstrap(infra_dir, repository_dir / operator_dir)


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
        AdministrativeBootstrap(
            tmp_path / "checkout" / "infra" / "bootstrap-admin", tmp_path / "operator"
        ).execute(**arguments)  # type: ignore[arg-type]
