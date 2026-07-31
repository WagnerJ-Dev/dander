"""Canonical metadata-spine and semantic-registry tests."""

from __future__ import annotations

import json
from pathlib import Path

from dander.catalog import MetadataSpine, SemanticRegistryPublisher
from dander.transform import TransformProject

_MODELS_DIR = Path(__file__).resolve().parents[2] / "models"


def test_spine_projects_relation_lineage_columns_and_test_contract() -> None:
    project = TransformProject.load(_MODELS_DIR, project_id="valid-project-123")
    (asset,) = MetadataSpine().compile(project, selected=["stg_greenhouse__jobs"])

    assert asset.relation == "valid-project-123.staging.stg_greenhouse__jobs"
    assert asset.upstream_relations == ("valid-project-123.raw.greenhouse_job_board_jobs",)
    assert asset.owner == "data-eng"
    assert asset.sensitivity == "public"
    assert asset.columns[0].name == "job_id"
    assert asset.columns[0].nullable is False
    assert asset.columns[1].nullable is True
    assert [(test.column, test.kind) for test in asset.tests] == [
        ("job_id", "not_null"),
        ("job_id", "unique"),
        ("title", "not_null"),
    ]


def test_manifest_is_versioned_sorted_and_has_no_volatile_timestamp() -> None:
    project = TransformProject.load(_MODELS_DIR, project_id="valid-project-123")
    spine = MetadataSpine()
    assets = spine.compile(project, selected=["stg_greenhouse__jobs"])

    first = spine.manifest(assets)
    second = spine.manifest(reversed(assets))

    assert first == second
    assert first["schema_version"] == 1
    assert first["projects"] == ["valid-project-123"]
    assert "generated_at" not in first


def test_registry_write_is_atomic_and_byte_stable(tmp_path: Path) -> None:
    project = TransformProject.load(_MODELS_DIR, project_id="valid-project-123")
    spine = MetadataSpine()
    manifest = spine.manifest(spine.compile(project, selected=["stg_greenhouse__jobs"]))
    output = tmp_path / "nested" / "catalog.json"
    publisher = SemanticRegistryPublisher()

    publisher.publish(manifest, output)
    first = output.read_bytes()
    publisher.publish(manifest, output)

    assert output.read_bytes() == first
    assert json.loads(first)["assets"][0]["name"] == "stg_greenhouse__jobs"
    assert list(output.parent.glob(".*.tmp")) == []
