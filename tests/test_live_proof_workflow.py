"""Safety and current-CLI coverage for the approval-gated live-proof path."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from scripts.live_proof.prepare_config import prepare_config
from scripts.live_proof.transforms import _run_job

if TYPE_CHECKING:
    import pytest


def _project(root: Path) -> Path:
    (root / "connectors").mkdir()
    (root / "models").mkdir()
    for source in ("greenhouse", "hubspot"):
        (root / "connectors" / f"{source}.yaml").write_text(
            f"""
name: {source}
base_url: https://example.test
auth_strategy: none
endpoints:
  - name: records
    path: /records
    raw_schema:
      - name: id
        type: STRING
""".strip(),
            encoding="utf-8",
        )
    for model in ("stg_greenhouse", "stg_hubspot"):
        (root / "models" / f"{model}.sql").write_text("SELECT 1\n", encoding="utf-8")
    path = root / "dander.yaml"
    path.write_text(
        """version: 1
pipelines:
  greenhouse_jobs:
    source: greenhouse
    models: [stg_greenhouse]
    paused: false
  hubspot_companies:
    source: hubspot
    models: [stg_hubspot]
    paused: false
""",
        encoding="utf-8",
    )
    return path


def test_prepare_config_pauses_every_pipeline_and_scopes_dataplex(tmp_path: Path) -> None:
    source = _project(tmp_path)
    output = tmp_path / "dander.live-proof.yaml"

    prepare_config(source, output, publish_dataplex_pipeline="hubspot_companies")

    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    pipelines = payload["pipelines"]
    assert all(pipeline["paused"] for pipeline in pipelines.values())
    assert all(pipeline["build_models"] for pipeline in pipelines.values())
    assert pipelines["greenhouse_jobs"]["publish_dataplex"] is False
    assert pipelines["hubspot_companies"]["publish_dataplex"] is True


def test_live_proof_workflow_uses_current_additive_cli_and_safe_inventory() -> None:
    workflow = Path(".github/workflows/live-proof.yml").read_text(encoding="utf-8")

    for removed_flag in (
        "--scheduler-paused",
        "--runtime-source",
        "--runtime-model",
        "--runtime-build-models",
        "--runtime-secret-id",
    ):
        assert removed_flag not in workflow
    assert "--config dander.live-proof.yaml" in workflow
    assert "prepare_config.py" in workflow
    assert "dander-greenhouse-public" in workflow
    assert "dander-hubspot-companies" in workflow
    assert '--job "$PROOF_JOB"' in workflow
    assert '--billing-account "$BILLING_ACCOUNT_ID"' in workflow
    assert "Record retained-resource inventory" in workflow
    assert workflow.index("Apply reviewed platform plan") < workflow.index(
        "Add HubSpot secret version"
    )
    final_verification = workflow.split("- name: Re-verify IAM and cost guard after proofs", 1)[1]
    final_verification = final_verification.split("- name: Record retained-resource inventory", 1)[
        0
    ]
    assert "--evidence-dir" not in final_verification


def test_transform_proof_targets_the_requested_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    def fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    _run_job("dander-greenhouse-public", "us-central1", "proof-project")

    assert commands == [
        (
            "gcloud",
            "run",
            "jobs",
            "execute",
            "dander-greenhouse-public",
            "--project",
            "proof-project",
            "--region",
            "us-central1",
            "--wait",
        )
    ]
