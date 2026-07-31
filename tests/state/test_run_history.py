"""Local and BigQuery run-history persistence tests."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from dander.state import RunStatus, SqliteRunHistoryStore

if TYPE_CHECKING:
    from pathlib import Path


def test_sqlite_run_history_persists_terminal_aggregates(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    store = SqliteRunHistoryStore(path)

    store.start("run-1", "greenhouse")
    store.finish(
        "run-1",
        RunStatus.SUCCEEDED,
        endpoints=2,
        extracted=12,
        affected=10,
    )

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT source, status, endpoints, extracted, affected FROM runs WHERE run_id = ?",
            ("run-1",),
        ).fetchone()
    assert row == ("greenhouse", "succeeded", 2, 12, 10)
