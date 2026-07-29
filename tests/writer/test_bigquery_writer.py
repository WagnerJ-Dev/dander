"""BigQuery SCD1 writer tests for DANDER-20."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from dander.writer import BigQueryReplaceWriter, BigQueryScd1Writer, BigQueryWriteError, WriteTarget

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from google.cloud import bigquery


class _Job:
    def __init__(self, *, affected: int | None = None, error: Exception | None = None) -> None:
        self.num_dml_affected_rows = affected
        self._error = error

    def result(self) -> object:
        if self._error is not None:
            raise self._error
        return self


class _Client:
    def __init__(self, *, load_error: Exception | None = None) -> None:
        self.load_error = load_error
        self.loaded_rows: list[dict[str, Any]] = []
        self.destination = ""
        self.queries: list[str] = []
        self.deleted: list[str] = []
        self.write_disposition: str | None = None

    def load_table_from_json(
        self,
        json_rows: Sequence[Mapping[str, Any]],
        destination: str,
        *,
        job_config: bigquery.LoadJobConfig,
    ) -> _Job:
        assert job_config.autodetect
        self.write_disposition = job_config.write_disposition
        self.loaded_rows = [dict(row) for row in json_rows]
        self.destination = destination
        return _Job(error=self.load_error)

    def query(self, query: str) -> _Job:
        self.queries.append(query)
        return _Job(affected=2 if query.startswith("MERGE") else None)

    def delete_table(self, table: str, *, not_found_ok: bool = False) -> None:
        assert not_found_ok
        self.deleted.append(table)


def _target() -> WriteTarget:
    return WriteTarget(
        project="unit-project",
        dataset="raw",
        table="example_widgets",
        business_key=("id",),
    )


def test_scd1_deduplicates_last_record_and_builds_explicit_merge() -> None:
    client = _Client()
    writer = BigQueryScd1Writer(project="unit-project", client=client)

    affected = writer.write(
        [
            {"id": "one", "label": "old"},
            {"id": "one", "label": "new"},
            {"id": "two", "label": "other"},
        ],
        _target(),
    )

    assert affected == 2
    assert client.loaded_rows == [
        {"id": "one", "label": "new"},
        {"id": "two", "label": "other"},
    ]
    assert client.queries[0].startswith(
        "CREATE TABLE IF NOT EXISTS `unit-project.raw.example_widgets`"
    )
    merge = client.queries[1]
    assert "ON target.`id` = source.`id`" in merge
    assert "target.`label` = source.`label`" in merge
    assert "SELECT *" not in merge
    assert client.deleted == [client.destination]


def test_writer_rejects_inconsistent_shape_before_network() -> None:
    client = _Client()
    writer = BigQueryScd1Writer(project="unit-project", client=client)

    with pytest.raises(BigQueryWriteError, match="different column set"):
        writer.write([{"id": "one"}, {"id": "two", "label": "extra"}], _target())

    assert not client.loaded_rows


def test_staging_table_is_cleaned_after_load_failure() -> None:
    client = _Client(load_error=RuntimeError("synthetic load failure"))
    writer = BigQueryScd1Writer(project="unit-project", client=client)

    with pytest.raises(RuntimeError, match="synthetic load failure"):
        writer.write([{"id": "one"}], _target())

    assert client.deleted == [client.destination]


def test_replace_writer_uses_direct_truncate_load_without_queries() -> None:
    client = _Client()
    writer = BigQueryReplaceWriter(project="unit-project", client=client)

    affected = writer.write([{"id": "one"}, {"id": "two"}], _target())

    assert affected == 2
    assert client.destination == "unit-project.raw.example_widgets"
    assert client.write_disposition == "WRITE_TRUNCATE"
    assert client.queries == []
    assert client.deleted == []


def test_replace_writer_deletes_stale_table_for_empty_snapshot() -> None:
    client = _Client()
    writer = BigQueryReplaceWriter(project="unit-project", client=client)

    assert writer.write([], _target()) == 0

    assert client.deleted == ["unit-project.raw.example_widgets"]
    assert client.queries == []
