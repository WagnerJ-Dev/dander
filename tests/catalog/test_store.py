"""Durable metadata snapshot store tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dander.catalog import SqliteMetadataStore

if TYPE_CHECKING:
    from pathlib import Path


def test_sqlite_metadata_store_replaces_pipeline_snapshot_atomically(tmp_path: Path) -> None:
    store = SqliteMetadataStore(tmp_path / "state.db")
    first = {"schema_version": 2, "pipeline_id": "jobs", "assets": []}
    second = {
        "schema_version": 2,
        "pipeline_id": "jobs",
        "assets": [{"name": "stg_jobs"}],
    }

    store.publish(pipeline_id="jobs", run_id="run-1", manifest=first)
    store.publish(pipeline_id="jobs", run_id="run-2", manifest=second)

    snapshots = store.snapshots(pipeline_id="jobs")
    assert len(snapshots) == 1
    assert snapshots[0].run_id == "run-2"
    assert snapshots[0].manifest == second
