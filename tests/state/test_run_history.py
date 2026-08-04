"""Local and BigQuery run-history persistence tests."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dander.state import BigQueryRunHistoryStore, RunStage, RunStatus, SqliteRunHistoryStore

if TYPE_CHECKING:
    from pathlib import Path

    from google.cloud import bigquery


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


def test_sqlite_run_history_reads_active_run(tmp_path: Path) -> None:
    store = SqliteRunHistoryStore(tmp_path / "state.db")
    store.start("run-active", "greenhouse", pipeline_id="greenhouse_jobs")

    record = store.recent(pipeline_id="greenhouse_jobs")[0]

    assert record.status is RunStatus.RUNNING
    assert record.stage is RunStage.INGEST
    assert record.finished_at is None


class _QueryJob:
    def result(self) -> tuple[object, ...]:
        return ()


@dataclass
class _BigQueryClient:
    queries: list[str] = field(default_factory=list)

    def query(
        self,
        query: str,
        *,
        job_config: bigquery.QueryJobConfig | None = None,
    ) -> _QueryJob:
        del job_config
        self.queries.append(query)
        return _QueryJob()


def test_bigquery_history_can_read_without_creating_or_altering_tables() -> None:
    client = _BigQueryClient()
    store = BigQueryRunHistoryStore(
        project="proof-project",
        dataset="dander_meta",
        client=client,
        initialize_on_read=False,
    )

    assert store.recent(limit=1, pipeline_id="graph_records") == ()
    assert len(client.queries) == 1
    assert client.queries[0].startswith("SELECT ")
    assert "CREATE" not in client.queries[0]
    assert "ALTER" not in client.queries[0]
