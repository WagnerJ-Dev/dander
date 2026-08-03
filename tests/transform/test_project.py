"""Transform project discovery, dependency, and compilation tests."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from dander.transform import TransformProject, TransformProjectError


def _write_model(
    root: Path,
    name: str,
    sql: str,
    *,
    materialization: str = "view",
    tests: str = "[]",
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.sql").write_text(dedent(sql))
    (root / f"{name}.yml").write_text(
        dedent(
            f"""
            model: {name}
            description: Safe test model.
            owner: data-eng
            materialization: {materialization}
            dataset: staging
            source_system: fixture
            sensitivity: public
            columns:
              - name: id
                type: STRING
                description: Fixture identifier.
            tests: {tests}
            """
        )
    )


def test_load_orders_selected_model_dependencies_and_compiles_refs(tmp_path: Path) -> None:
    _write_model(
        tmp_path,
        "base",
        "SELECT CAST(id AS STRING) AS id FROM {{ ref('raw_fixture') }}",
    )
    _write_model(
        tmp_path,
        "consumer",
        "SELECT id FROM {{ ref('base') }}",
    )

    project = TransformProject.load(tmp_path, project_id="valid-project-123")
    ordered = project.ordered(["consumer"])

    assert [model.name for model in ordered] == ["base", "consumer"]
    assert project.compile(ordered[0]) == (
        "SELECT CAST(id AS STRING) AS id FROM `valid-project-123.raw.fixture`"
    )
    assert project.compile(ordered[1]) == ("SELECT id FROM `valid-project-123.staging.base`")


def test_unknown_reference_fails_during_project_load(tmp_path: Path) -> None:
    _write_model(tmp_path, "broken", "SELECT id FROM {{ ref('missing') }}")

    with pytest.raises(TransformProjectError, match="Unknown model reference: missing"):
        TransformProject.load(tmp_path, project_id="valid-project-123")


def test_cycle_fails_before_compilation(tmp_path: Path) -> None:
    _write_model(tmp_path, "first", "SELECT id FROM {{ ref('second') }}")
    _write_model(tmp_path, "second", "SELECT id FROM {{ ref('first') }}")
    project = TransformProject.load(tmp_path, project_id="valid-project-123")

    with pytest.raises(TransformProjectError, match="first -> second -> first"):
        project.ordered(["first"])


def test_model_name_must_match_sql_filename(tmp_path: Path) -> None:
    _write_model(tmp_path, "expected", "SELECT 'x' AS id")
    metadata = (tmp_path / "expected.yml").read_text()
    (tmp_path / "expected.yml").write_text(metadata.replace("model: expected", "model: other"))

    with pytest.raises(TransformProjectError, match="does not match SQL file"):
        TransformProject.load(tmp_path, project_id="valid-project-123")


def test_missing_sidecar_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "orphan.sql").write_text("SELECT 'x' AS id")

    with pytest.raises(TransformProjectError, match="Missing YAML sidecar"):
        TransformProject.load(tmp_path, project_id="valid-project-123")


def test_metadata_validation_does_not_echo_authored_value(tmp_path: Path) -> None:
    _write_model(tmp_path, "safe", "SELECT 'x' AS id")
    metadata = (tmp_path / "safe.yml").read_text()
    (tmp_path / "safe.yml").write_text(metadata.replace("owner: data-eng", "owner: ''"))

    with pytest.raises(TransformProjectError) as raised:
        TransformProject.load(tmp_path, project_id="valid-project-123")

    assert "owner" in str(raised.value)
    assert "data-eng" not in str(raised.value)


def test_model_must_compile_to_read_only_query(tmp_path: Path) -> None:
    _write_model(tmp_path, "unsafe", "DELETE FROM `project.dataset.table` WHERE TRUE")
    project = TransformProject.load(tmp_path, project_id="valid-project-123")

    with pytest.raises(TransformProjectError, match="read-only query"):
        project.compile(project.models["unsafe"])


def test_unknown_selected_model_fails(tmp_path: Path) -> None:
    _write_model(tmp_path, "known", "SELECT 'x' AS id")
    project = TransformProject.load(tmp_path, project_id="valid-project-123")

    with pytest.raises(TransformProjectError, match="Unknown selected models: absent"):
        project.ordered(["absent"])


def test_salesforce_accounts_model_loads_and_compiles_raw_relation() -> None:
    models = Path(__file__).parents[2] / "models"
    project = TransformProject.load(models, project_id="valid-project-123")
    model = project.models["stg_salesforce__accounts"]

    assert project.ordered([model.name]) == (model,)
    assert "`valid-project-123.raw.salesforce_accounts`" in project.compile(model)
    assert [metric.name for metric in model.metadata.metrics] == ["account_count"]


def test_servicenow_incidents_model_loads_and_casts_internal_utc_values() -> None:
    models = Path(__file__).parents[2] / "models"
    project = TransformProject.load(models, project_id="valid-project-123")
    model = project.models["stg_servicenow__incidents"]

    assert project.ordered([model.name]) == (model,)
    compiled = project.compile(model)
    assert "`valid-project-123.raw.servicenow_incidents`" in compiled
    assert "PARSE_TIMESTAMP('%F %H:%M:%S', sys_updated_on)" in compiled
    assert [metric.name for metric in model.metadata.metrics] == ["incident_count"]
