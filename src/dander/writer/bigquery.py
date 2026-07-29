"""Idempotent BigQuery SCD1 and full-replacement writers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Protocol, cast
from uuid import uuid4

from google.cloud import bigquery

from dander.writer.base import WriteMode, WritePattern, WriteTarget

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class BigQueryWriteError(ValueError):
    """Raised when a batch cannot satisfy the SCD1 write contract."""


class _Job(Protocol):
    num_dml_affected_rows: int | None

    def result(self) -> object:
        """Wait for job completion."""


class _BigQueryClient(Protocol):
    def load_table_from_json(
        self,
        json_rows: Sequence[Mapping[str, Any]],
        destination: str,
        *,
        job_config: bigquery.LoadJobConfig,
    ) -> _Job:
        """Load JSON-compatible rows."""

    def query(self, query: str) -> _Job:
        """Run a SQL query."""

    def delete_table(self, table: str, *, not_found_ok: bool = False) -> None:
        """Delete a table."""


class BigQueryScd1Writer(WritePattern):
    """Load a batch through a unique staging table and merge on its business key."""

    mode = WriteMode.SCD1

    def __init__(self, *, project: str, client: _BigQueryClient | None = None) -> None:
        self._project = _validated_identifier(project, "project", allow_dash=True)
        self._client = client or cast("_BigQueryClient", bigquery.Client(project=project))

    def write(self, records: Iterable[Mapping[str, Any]], target: WriteTarget) -> int:
        """Write a consistently-shaped batch idempotently.

        Duplicate business keys within the incoming batch use last-record-wins semantics before
        loading. This prevents BigQuery `MERGE` from matching a target row more than once.
        """
        target_id = _target_id(target)
        if target.project != self._project:
            raise BigQueryWriteError(
                f"Writer project {self._project!r} does not match target project {target.project!r}"
            )
        if not target.business_key:
            raise BigQueryWriteError("SCD1 writes require at least one business-key column")

        rows = [dict(record) for record in records]
        if not rows:
            return 0

        columns = tuple(rows[0])
        if not columns:
            raise BigQueryWriteError("Cannot write records with no columns")
        for column in columns:
            _validated_identifier(column, "column")
        for key in target.business_key:
            _validated_identifier(key, "business-key column")
            if key not in columns:
                raise BigQueryWriteError(f"Business-key column {key!r} is absent from the batch")

        expected_columns = set(columns)
        deduplicated: dict[tuple[object, ...], dict[str, Any]] = {}
        for index, row in enumerate(rows):
            if set(row) != expected_columns:
                raise BigQueryWriteError(
                    f"Record {index} has a different column set from the first record"
                )
            key_values = tuple(row[key] for key in target.business_key)
            if any(value is None for value in key_values):
                raise BigQueryWriteError(f"Record {index} has a null business-key value")
            try:
                deduplicated[key_values] = row
            except TypeError as error:
                raise BigQueryWriteError(
                    f"Record {index} has a non-scalar business-key value"
                ) from error

        staged_rows = list(deduplicated.values())
        staging_id = f"{target.project}.{target.dataset}._dander_stage_{target.table}_{uuid4().hex}"
        load_config = bigquery.LoadJobConfig(
            autodetect=True,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )

        try:
            self._client.load_table_from_json(
                staged_rows,
                staging_id,
                job_config=load_config,
            ).result()
            self._client.query(_create_target_sql(target_id, staging_id, columns)).result()
            merge_job = self._client.query(
                _merge_sql(target_id, staging_id, columns, target.business_key)
            )
            merge_job.result()
            return (
                merge_job.num_dml_affected_rows
                if merge_job.num_dml_affected_rows is not None
                else len(staged_rows)
            )
        finally:
            self._client.delete_table(staging_id, not_found_ok=True)


class BigQueryReplaceWriter(WritePattern):
    """Replace a table using only BigQuery load and table-management APIs."""

    mode = WriteMode.REPLACE

    def __init__(self, *, project: str, client: _BigQueryClient | None = None) -> None:
        self._project = _validated_identifier(project, "project", allow_dash=True)
        self._client = client or cast("_BigQueryClient", bigquery.Client(project=project))

    def write(self, records: Iterable[Mapping[str, Any]], target: WriteTarget) -> int:
        """Replace the target without SQL or DML, including clearing an empty snapshot."""
        target_id = _target_id(target)
        if target.project != self._project:
            raise BigQueryWriteError(
                f"Writer project {self._project!r} does not match target project {target.project!r}"
            )

        rows = [dict(record) for record in records]
        if not rows:
            self._client.delete_table(target_id, not_found_ok=True)
            return 0

        columns = tuple(rows[0])
        if not columns:
            raise BigQueryWriteError("Cannot write records with no columns")
        for column in columns:
            _validated_identifier(column, "column")
        expected_columns = set(columns)
        for index, row in enumerate(rows):
            if set(row) != expected_columns:
                raise BigQueryWriteError(
                    f"Record {index} has a different column set from the first record"
                )

        load_config = bigquery.LoadJobConfig(
            autodetect=True,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        self._client.load_table_from_json(
            rows,
            target_id,
            job_config=load_config,
        ).result()
        return len(rows)


def _validated_identifier(value: str, label: str, *, allow_dash: bool = False) -> str:
    pattern = r"^[A-Za-z_][A-Za-z0-9_-]*$" if allow_dash else _IDENTIFIER.pattern
    if not re.fullmatch(pattern, value):
        raise BigQueryWriteError(f"Invalid {label}: {value!r}")
    return value


def _target_id(target: WriteTarget) -> str:
    project = _validated_identifier(target.project, "project", allow_dash=True)
    dataset = _validated_identifier(target.dataset, "dataset")
    table = _validated_identifier(target.table, "table")
    return f"{project}.{dataset}.{table}"


def _quoted_columns(columns: Sequence[str], *, alias: str | None = None) -> str:
    prefix = f"{alias}." if alias else ""
    return ", ".join(f"{prefix}`{column}`" for column in columns)


def _create_target_sql(target_id: str, staging_id: str, columns: Sequence[str]) -> str:
    selected = _quoted_columns(columns)
    return (
        f"CREATE TABLE IF NOT EXISTS `{target_id}` AS "
        f"SELECT {selected} FROM `{staging_id}` WHERE FALSE"
    )


def _merge_sql(
    target_id: str,
    staging_id: str,
    columns: Sequence[str],
    business_key: Sequence[str],
) -> str:
    match = " AND ".join(f"target.`{key}` = source.`{key}`" for key in business_key)
    mutable_columns = [column for column in columns if column not in business_key]
    matched = ""
    if mutable_columns:
        assignments = ", ".join(
            f"target.`{column}` = source.`{column}`" for column in mutable_columns
        )
        matched = f"\nWHEN MATCHED THEN UPDATE SET {assignments}"
    insert_columns = _quoted_columns(columns)
    insert_values = _quoted_columns(columns, alias="source")
    return (
        f"MERGE `{target_id}` AS target\n"
        f"USING `{staging_id}` AS source\n"
        f"ON {match}"
        f"{matched}\n"
        f"WHEN NOT MATCHED THEN INSERT ({insert_columns}) VALUES ({insert_values})"
    )
