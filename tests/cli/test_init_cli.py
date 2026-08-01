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
            "--secret-id",
            "api-token",
            "--github-repository",
            "WagnerJ-Dev/dander",
            "--enable-cost-guard",
            "--cost-guard-budget-amount",
            "4.50",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["enable_runtime"] is True
    pipelines = captured["pipelines"]
    assert isinstance(pipelines, dict)
    assert set(pipelines) == {"greenhouse_jobs", "hubspot_companies"}
    assert pipelines["greenhouse_jobs"]["paused"] is False
    assert pipelines["hubspot_companies"]["paused"] is True
    assert captured["secret_ids"] == ("api-token",)
    assert captured["github_repository"] == "WagnerJ-Dev/dander"
    assert captured["enable_cost_guard"] is True
    assert captured["cost_guard_budget_amount"] == "4.50"
    assert captured["live_cost_guard"] is False


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


def test_live_cost_guard_is_named_in_apply_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_execute(self: object, **kwargs: object) -> Path:
        raise AssertionError("must not execute")

    monkeypatch.setattr("dander.cli.main.TerraformBootstrap.execute", fake_execute)

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--project",
            "unit-project",
            "--state-bucket",
            "unit-state",
            "--enable-cost-guard",
            "--billing-account",
            "ABCDEF-123456-ABCDEF",
            "--live-cost-guard",
            "--apply",
        ],
        input="n\n",
    )

    assert "LIVE automatic billing detachment" in result.output


def test_init_apply_bootstraps_state_identity_image_and_platform(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    captured: dict[str, object] = {}

    def fake_bucket(self: object, **kwargs: object) -> bool:
        events.append("state")
        assert kwargs["bucket"] == "unit-project-dander-state"
        return True

    def fake_admin(self: object, **kwargs: object) -> Path:
        events.append("admin")
        assert kwargs["adopt_state_bucket"] is True
        return tmp_path / "admin.tfplan"

    def fake_publish(self: object, **kwargs: object) -> str:
        events.append("image")
        return "us-central1-docker.pkg.dev/unit-project/dander/dander@sha256:" + "a" * 64

    def fake_platform(self: object, **kwargs: object) -> Path:
        events.append("platform")
        captured.update(kwargs)
        return tmp_path / "platform.tfplan"

    monkeypatch.setattr("dander.cli.main.StateBucketBootstrap.ensure", fake_bucket)
    monkeypatch.setattr("dander.cli.main.AdministrativeBootstrap.execute", fake_admin)
    monkeypatch.setattr("dander.cli.main.RuntimeImagePublisher.publish", fake_publish)
    monkeypatch.setattr(
        "dander.cli.main.active_admin_member",
        lambda **_kwargs: "user:operator@example.invalid",
    )
    monkeypatch.setattr("dander.cli.main.TerraformBootstrap.execute", fake_platform)

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--project",
            "unit-project",
            "--billing-account",
            "ABCDEF-123456-ABCDEF",
            "--operator-artifact-dir",
            str(tmp_path / "operator"),
            "--apply",
        ],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    assert events == ["state", "admin", "image", "platform"]
    assert captured["enable_runtime"] is True
    assert captured["enable_cost_guard"] is True
    assert captured["bootstrap_service_account"] == (
        "dander-bootstrap@unit-project.iam.gserviceaccount.com"
    )
