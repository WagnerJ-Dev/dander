"""Watermark / control state — last successful cursor per (source, entity).

Enables idempotent restarts: a re-run resumes from the last committed cursor rather than
re-pulling or corrupting data. Backed by BigQuery or Firestore. See ``steering/02-engineering.md``.
"""

from __future__ import annotations

import re
import sqlite3
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, cast

from google.cloud import bigquery

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path


class WatermarkStore(ABC):
    """Persists the incremental cursor for each (source, entity) pair."""

    @abstractmethod
    def get(self, source: str, entity: str) -> str | None:
        """Return the last successful cursor value, or ``None`` if never run."""

    @abstractmethod
    def set(self, source: str, entity: str, cursor: str) -> None:
        """Persist ``cursor`` after a successful load (called only on commit)."""


class _QueryJob(Protocol):
    def result(self) -> Iterable[Mapping[str, Any]]:
        """Wait for query completion and return rows."""


class _BigQueryClient(Protocol):
    def query(
        self,
        query: str,
        *,
        job_config: bigquery.QueryJobConfig | None = None,
    ) -> _QueryJob:
        """Run a BigQuery statement."""


class BigQueryWatermarkStore(WatermarkStore):
    """Persist committed cursors in a BigQuery control table."""

    def __init__(
        self,
        *,
        project: str,
        dataset: str,
        client: _BigQueryClient | None = None,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", project):
            raise ValueError(f"Invalid BigQuery project: {project!r}")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", dataset):
            raise ValueError(f"Invalid BigQuery dataset: {dataset!r}")
        self._table_id = f"{project}.{dataset}._dander_watermarks"
        self._client = client or cast("_BigQueryClient", bigquery.Client(project=project))
        self._table_ready = False

    def get(self, source: str, entity: str) -> str | None:
        """Return the most recently committed cursor for `(source, entity)`."""
        self._ensure_table()
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("source", "STRING", source),
                bigquery.ScalarQueryParameter("entity", "STRING", entity),
            ]
        )
        rows = list(
            self._client.query(
                (
                    f"SELECT last_cursor FROM `{self._table_id}` "
                    "WHERE source_name = @source AND entity_name = @entity "
                    "LIMIT 1"
                ),
                job_config=config,
            ).result()
        )
        if not rows:
            return None
        cursor = rows[0]["last_cursor"]
        return str(cursor) if cursor is not None else None

    def set(self, source: str, entity: str, cursor: str) -> None:
        """Atomically insert or replace a committed cursor."""
        self._ensure_table()
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("source", "STRING", source),
                bigquery.ScalarQueryParameter("entity", "STRING", entity),
                bigquery.ScalarQueryParameter("cursor", "STRING", cursor),
            ]
        )
        self._client.query(
            (
                f"MERGE `{self._table_id}` AS target "
                "USING (SELECT @source AS source_name, @entity AS entity_name, "
                "@cursor AS last_cursor) AS incoming "
                "ON target.source_name = incoming.source_name "
                "AND target.entity_name = incoming.entity_name "
                "WHEN MATCHED THEN UPDATE SET "
                "last_cursor = incoming.last_cursor, updated_at = CURRENT_TIMESTAMP() "
                "WHEN NOT MATCHED THEN INSERT "
                "(source_name, entity_name, last_cursor, updated_at) "
                "VALUES (incoming.source_name, incoming.entity_name, "
                "incoming.last_cursor, CURRENT_TIMESTAMP())"
            ),
            job_config=config,
        ).result()

    def _ensure_table(self) -> None:
        if self._table_ready:
            return
        self._client.query(
            f"CREATE TABLE IF NOT EXISTS `{self._table_id}` ("
            "source_name STRING NOT NULL, "
            "entity_name STRING NOT NULL, "
            "last_cursor STRING NOT NULL, "
            "updated_at TIMESTAMP NOT NULL"
            ") "
            "CLUSTER BY source_name, entity_name"
        ).result()
        self._table_ready = True


class SqliteWatermarkStore(WatermarkStore):
    """Persist local sandbox cursors in a small SQLite database."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS watermarks ("
                "source TEXT NOT NULL, "
                "entity TEXT NOT NULL, "
                "cursor TEXT NOT NULL, "
                "PRIMARY KEY (source, entity)"
                ")"
            )

    def get(self, source: str, entity: str) -> str | None:
        """Return a locally recorded cursor, if present."""
        with sqlite3.connect(self._path) as connection:
            row = connection.execute(
                "SELECT cursor FROM watermarks WHERE source = ? AND entity = ?",
                (source, entity),
            ).fetchone()
        return str(row[0]) if row else None

    def set(self, source: str, entity: str, cursor: str) -> None:
        """Insert or replace a local cursor atomically."""
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "INSERT INTO watermarks (source, entity, cursor) VALUES (?, ?, ?) "
                "ON CONFLICT(source, entity) DO UPDATE SET cursor = excluded.cursor",
                (source, entity, cursor),
            )
