"""Project manifest validation and Terraform expansion tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from dander.project import ProjectConfigError, load_project_config


def test_repository_manifest_defines_additive_greenhouse_and_hubspot() -> None:
    project = load_project_config(Path("dander.yaml"))
    project.validate_references(Path.cwd())

    assert project.platform.region == "us-central1"
    assert project.platform.bigquery_location == "US"
    assert project.platform.runtime.model_dump() == {
        "cpu": 1,
        "memory": "512Mi",
        "timeout_seconds": 300,
        "max_retries": 1,
        "batch_rows": 10_000,
    }
    assert project.platform.safety.require_guarded_free_tier is True
    expanded = project.terraform_pipelines()
    assert set(expanded) == {"greenhouse_jobs", "hubspot_companies"}
    assert expanded["greenhouse_jobs"]["job_name"] == "dander-greenhouse-public"
    assert expanded["greenhouse_jobs"]["secret_env"] == {}
    assert expanded["hubspot_companies"]["job_name"] == "dander-hubspot-companies"
    assert expanded["hubspot_companies"]["secret_env"] == {
        "HUBSPOT_PRIVATE_APP_TOKEN": "hubspot-private-app-token"
    }


def test_generated_resource_names_are_stable_and_bounded(tmp_path: Path) -> None:
    config = tmp_path / "dander.yaml"
    connector_dir = tmp_path / "connectors"
    model_dir = tmp_path / "models"
    connector_dir.mkdir()
    model_dir.mkdir()
    (connector_dir / "source.yaml").write_text("name: source\n", encoding="utf-8")
    (model_dir / "model.sql").write_text("SELECT 1\n", encoding="utf-8")
    config.write_text(
        """
version: 1
pipelines:
  long_pipeline_identifier_for_bounded_names:
    source: source
    models: [model]
""".strip(),
        encoding="utf-8",
    )

    project = load_project_config(config)
    project.validate_references(tmp_path)
    expanded = project.terraform_pipelines()["long_pipeline_identifier_for_bounded_names"]
    assert len(str(expanded["job_name"])) <= 63
    assert len(str(expanded["runtime_service_account_id"])) <= 30
    assert len(str(expanded["scheduler_service_account_id"])) <= 30


def test_missing_model_is_reported_by_pipeline_structure_only(tmp_path: Path) -> None:
    (tmp_path / "connectors").mkdir()
    (tmp_path / "models").mkdir()
    (tmp_path / "connectors" / "source.yaml").write_text("name: source\n", encoding="utf-8")
    config = tmp_path / "dander.yaml"
    config.write_text(
        "version: 1\npipelines:\n  example:\n    source: source\n    models: [missing]\n",
        encoding="utf-8",
    )

    project = load_project_config(config)
    with pytest.raises(ProjectConfigError, match="Pipeline 'example'.*missing model 'missing'"):
        project.validate_references(tmp_path)


def test_project_config_rejects_literal_secret_values(tmp_path: Path) -> None:
    config = tmp_path / "dander.yaml"
    config.write_text(
        """
version: 1
pipelines:
  example:
    source: source
    models: [model]
    secrets:
      Authorization: pat-secret-value
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ProjectConfigError, match="pipelines.example.secrets"):
        load_project_config(config)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cpu", 3),
        ("memory", "512MB"),
        ("timeout_seconds", 0),
        ("max_retries", 11),
        ("batch_rows", 100_001),
    ],
)
def test_project_config_rejects_invalid_runtime_values(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    config = tmp_path / "dander.yaml"
    config.write_text(
        f"""
version: 1
platform:
  runtime:
    {field}: {value}
pipelines:
  example:
    source: source
    models: [model]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ProjectConfigError, match=rf"platform.runtime.{field}"):
        load_project_config(config)
