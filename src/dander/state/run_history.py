"""Non-sensitive operational run history for local and BigQuery runtimes."""

from __future__ import annotations

import re
import sqlite3
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, cast

from google.cloud import bigquery

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class RunStatus(StrEnum):
    """Terminal state recorded for one pipeline run."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunHistoryStore(ABC):
    """Persist lifecycle summaries without row values, cursors, or error messages."""

    @abstractmethod
    def start(self, run_id: str, source: str) -> None:
        """Record that a run started."""

    @abstractmethod
    def finish(
        self,
        run_id: str,
        status: RunStatus,
        *,
        endpoints: int,
        extracted: int,
        affected: int,
    ) -> None:
        """Record a terminal aggregate for a run."""


class _Job(Protocol):
    def result(self) -> Iterable[object]:
        """Wait for query completion."""


class _Client(Protocol):
    def query(
        self,
        query: str,
        *,
        job_config: bigquery.QueryJobConfig | None = None,
    ) -> _Job:
        """Run a parameterized statement."""


class BigQueryRunHistoryStore(RunHistoryStore):
    """Persist run lifecycle summaries in a clustered BigQuery control table."""

    def __init__(self, *, project: str, dataset: str, client: _Client | None = None) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", project):
            raise ValueError(f"Invalid BigQuery project: {project!r}")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", dataset):
            raise ValueError(f"Invalid BigQuery dataset: {dataset!r}")
        self._table = f"{project}.{dataset}._dander_runs"
        self._client = client or cast("_Client", bigquery.Client(project=project))
        self._ready = False

    def start(self, run_id: str, source: str) -> None:
        self._ensure_table()
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("source", "STRING", source),
            ]
        )
        self._client.query(
            f"INSERT INTO `{self._table}` "
            "(run_id, source_name, status, started_at, finished_at, "
            "endpoints, extracted, affected) "
            "VALUES (@run_id, @source, 'running', CURRENT_TIMESTAMP(), NULL, 0, 0, 0)",
            job_config=config,
        ).result()

    def finish(
        self,
        run_id: str,
        status: RunStatus,
        *,
        endpoints: int,
        extracted: int,
        affected: int,
    ) -> None:
        self._ensure_table()
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", run_id),
                bigquery.ScalarQueryParameter("status", "STRING", status.value),
                bigquery.ScalarQueryParameter("endpoints", "INT64", endpoints),
                bigquery.ScalarQueryParameter("extracted", "INT64", extracted),
                bigquery.ScalarQueryParameter("affected", "INT64", affected),
            ]
        )
        self._client.query(
            f"UPDATE `{self._table}` SET status = @status, finished_at = CURRENT_TIMESTAMP(), "
            "endpoints = @endpoints, extracted = @extracted, affected = @affected "
            "WHERE run_id = @run_id",
            job_config=config,
        ).result()

    def _ensure_table(self) -> None:
        if self._ready:
            return
        self._client.query(
            f"CREATE TABLE IF NOT EXISTS `{self._table}` ("
            "run_id STRING NOT NULL, source_name STRING NOT NULL, status STRING NOT NULL, "
            "started_at TIMESTAMP NOT NULL, finished_at TIMESTAMP, endpoints INT64 NOT NULL, "
            "extracted INT64 NOT NULL, affected INT64 NOT NULL) "
            "CLUSTER BY source_name, status"
        ).result()
        self._ready = True


class SqliteRunHistoryStore(RunHistoryStore):
    """Persist sandbox run summaries beside local watermark state."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS runs ("
                "run_id TEXT PRIMARY KEY, source TEXT NOT NULL, status TEXT NOT NULL, "
                "started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, "
                "endpoints INTEGER NOT NULL DEFAULT 0, extracted INTEGER NOT NULL DEFAULT 0, "
                "affected INTEGER NOT NULL DEFAULT 0)"
            )

    def start(self, run_id: str, source: str) -> None:
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "INSERT INTO runs (run_id, source, status) VALUES (?, ?, 'running')",
                (run_id, source),
            )

    def finish(
        self,
        run_id: str,
        status: RunStatus,
        *,
        endpoints: int,
        extracted: int,
        affected: int,
    ) -> None:
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "UPDATE runs SET status = ?, finished_at = CURRENT_TIMESTAMP, "
                "endpoints = ?, extracted = ?, affected = ? WHERE run_id = ?",
                (status.value, endpoints, extracted, affected, run_id),
            )
