"""Local and BigQuery run-history persistence tests."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from dander.state import RunStage, RunStatus, SqliteRunHistoryStore

if TYPE_CHECKING:
    from pathlib import Path


def test_sqlite_run_history_persists_terminal_aggregates(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    store = SqliteRunHistoryStore(path)

    store.start("run-1", "greenhouse", pipeline_id="greenhouse_jobs")
    store.checkpoint(
        "run-1",
        RunStage.METADATA,
        endpoints=2,
        extracted=12,
        affected=10,
        models=1,
        assertions=2,
    )
    store.finish(
        "run-1",
        RunStatus.SUCCEEDED,
        endpoints=2,
        extracted=12,
        affected=10,
        models=1,
        assertions=2,
        assets=1,
    )

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT source, status, stage, endpoints, extracted, affected, models, assertions, "
            "assets FROM runs WHERE run_id = ?",
            ("run-1",),
        ).fetchone()
    assert row == ("greenhouse", "succeeded", "complete", 2, 12, 10, 1, 2, 1)
    records = store.recent(pipeline_id="greenhouse_jobs")
    assert len(records) == 1
    assert records[0].pipeline_id == "greenhouse_jobs"
    assert records[0].stage is RunStage.COMPLETE


def test_sqlite_run_history_records_overlap_as_skipped_complete(tmp_path: Path) -> None:
    store = SqliteRunHistoryStore(tmp_path / "state.db")
    store.start("run-skipped", "hubspot", pipeline_id="hubspot_companies")

    store.finish(
        "run-skipped",
        RunStatus.SKIPPED,
        endpoints=0,
        extracted=0,
        affected=0,
    )

    record = store.recent(pipeline_id="hubspot_companies")[0]
    assert record.status is RunStatus.SKIPPED
    assert record.stage is RunStage.COMPLETE
    assert record.failure_stage is None
