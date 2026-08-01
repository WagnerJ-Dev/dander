"""BigQuery SCD1 writer tests for DANDER-20."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from dander.writer import (
    BigQueryIncrementalWriter,
    BigQueryReplaceWriter,
    BigQueryScd1Writer,
    BigQueryScd2Writer,
    BigQuerySnapshotWriter,
    BigQueryWriteError,
    SchemaEvolution,
    WriteField,
    WriteMode,
    WritePattern,
    WriteTarget,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

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
        self.loaded_batches: list[list[dict[str, Any]]] = []
        self.destination = ""
        self.queries: list[str] = []
        self.deleted: list[str] = []
        self.write_disposition: str | None = None
        self.write_dispositions: list[str] = []

    def load_table_from_json(
        self,
        json_rows: Sequence[Mapping[str, Any]],
        destination: str,
        *,
        job_config: bigquery.LoadJobConfig,
    ) -> _Job:
        assert job_config.autodetect
        self.write_disposition = job_config.write_disposition
        self.write_dispositions.append(job_config.write_disposition)
        self.loaded_rows = [dict(row) for row in json_rows]
        self.loaded_batches.append(self.loaded_rows)
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
    assert client.queries[0].startswith(f"ALTER TABLE `{client.destination}` SET OPTIONS")
    assert client.queries[1].startswith(
        "CREATE TABLE IF NOT EXISTS `unit-project.raw.example_widgets`"
    )
    merge = client.queries[2]
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


def test_replace_writer_stages_then_atomically_replaces_target() -> None:
    client = _Client()
    writer = BigQueryReplaceWriter(project="unit-project", client=client)

    affected = writer.write([{"id": "one"}, {"id": "two"}], _target())

    assert affected == 2
    assert client.destination.startswith("unit-project.raw._dander_stage_example_widgets_")
    assert client.write_disposition == "WRITE_TRUNCATE"
    assert client.queries[0].startswith(f"ALTER TABLE `{client.destination}` SET OPTIONS")
    assert client.queries[1] == (
        "CREATE OR REPLACE TABLE `unit-project.raw.example_widgets` AS "
        f"SELECT `id` FROM `{client.destination}`"
    )
    assert client.deleted == [client.destination]


def test_replace_writer_deletes_stale_table_for_empty_snapshot() -> None:
    client = _Client()
    writer = BigQueryReplaceWriter(project="unit-project", client=client)

    assert writer.write([], _target()) == 0

    assert client.deleted == ["unit-project.raw.example_widgets"]
    assert client.queries == []


def test_replace_writer_bounds_load_requests_and_appends_after_first_chunk() -> None:
    client = _Client()
    writer = BigQueryReplaceWriter(
        project="unit-project",
        client=client,
        max_batch_rows=2,
    )

    affected = writer.write(
        [{"id": "one"}, {"id": "two"}, {"id": "three"}, {"id": "four"}, {"id": "five"}],
        _target(),
    )

    assert affected == 5
    assert [len(batch) for batch in client.loaded_batches] == [2, 2, 1]
    assert client.write_dispositions == ["WRITE_TRUNCATE", "WRITE_APPEND", "WRITE_APPEND"]
    assert client.queries[-1].startswith("CREATE OR REPLACE TABLE")
    assert client.deleted == [client.destination]


def test_replace_writer_starts_loading_before_input_is_exhausted() -> None:
    observed_at_load: list[int] = []
    yielded = 0

    class _ObservingClient(_Client):
        def load_table_from_json(
            self,
            json_rows: Sequence[Mapping[str, Any]],
            destination: str,
            *,
            job_config: bigquery.LoadJobConfig,
        ) -> _Job:
            observed_at_load.append(yielded)
            return super().load_table_from_json(
                json_rows,
                destination,
                job_config=job_config,
            )

    def records() -> Iterable[Mapping[str, Any]]:
        nonlocal yielded
        for index in range(5):
            yielded += 1
            yield {"id": str(index)}

    client = _ObservingClient()
    writer = BigQueryReplaceWriter(
        project="unit-project",
        client=client,
        max_batch_rows=2,
    )

    assert writer.write(records(), _target()) == 5
    assert observed_at_load == [2, 4, 5]


def test_replace_writer_does_not_publish_partial_stage_after_source_failure() -> None:
    client = _Client()
    writer = BigQueryReplaceWriter(
        project="unit-project",
        client=client,
        max_batch_rows=2,
    )

    def records() -> Iterable[Mapping[str, Any]]:
        yield {"id": "one"}
        yield {"id": "two"}
        raise RuntimeError("synthetic extraction failure")

    with pytest.raises(RuntimeError, match="synthetic extraction failure"):
        writer.write(records(), _target())

    assert len(client.loaded_batches) == 1
    assert all(not query.startswith("CREATE OR REPLACE TABLE") for query in client.queries)
    assert client.deleted == [client.destination]


def test_writer_rejects_invalid_batch_bound() -> None:
    with pytest.raises(BigQueryWriteError, match="positive integer"):
        BigQueryScd1Writer(project="unit-project", client=_Client(), max_batch_rows=0)


def test_additive_schema_evolution_adds_only_declared_scalar_columns() -> None:
    client = _Client()
    writer = BigQueryScd1Writer(
        project="unit-project",
        client=client,
        schema_evolution=SchemaEvolution.ADDITIVE,
    )
    target = WriteTarget(
        project="unit-project",
        dataset="raw",
        table="example_widgets",
        business_key=("id",),
        schema=(
            WriteField(name="id", data_type="STRING"),
            WriteField(name="label", data_type="STRING"),
        ),
    )

    writer.write([{"id": "one", "label": "new"}], target)

    evolution = client.queries[2]
    assert evolution == (
        "ALTER TABLE `unit-project.raw.example_widgets` "
        "ADD COLUMN IF NOT EXISTS `id` STRING;\n"
        "ALTER TABLE `unit-project.raw.example_widgets` "
        "ADD COLUMN IF NOT EXISTS `label` STRING"
    )
    assert client.queries[3].startswith("MERGE")


def test_additive_schema_rejects_unsupported_type_before_load() -> None:
    client = _Client()
    writer = BigQueryScd1Writer(
        project="unit-project",
        client=client,
        schema_evolution=SchemaEvolution.ADDITIVE,
    )
    target = WriteTarget(
        project="unit-project",
        dataset="raw",
        table="example_widgets",
        business_key=("id",),
        schema=(WriteField(name="id", data_type="STRUCT<value STRING>"),),
    )

    with pytest.raises(BigQueryWriteError, match="Unsupported additive schema type"):
        writer.write([{"id": "one"}], target)

    assert client.loaded_batches == []


def test_incremental_writer_requires_cursor_and_reuses_idempotent_merge() -> None:
    client = _Client()
    writer = BigQueryIncrementalWriter(
        project="unit-project",
        cursor_field="updated_at",
        client=client,
    )

    affected = writer.write(
        [{"id": "one", "updated_at": "2026-07-29T12:00:00Z"}],
        _target(),
    )

    assert writer.mode is WriteMode.INCREMENTAL
    assert affected == 2
    assert client.queries[2].startswith("MERGE")

    with pytest.raises(BigQueryWriteError, match="Cursor column"):
        writer.write([{"id": "two"}], _target())
    with pytest.raises(BigQueryWriteError, match="null cursor"):
        writer.write([{"id": "two", "updated_at": None}], _target())


def test_snapshot_writer_partitions_and_suppresses_exact_reruns() -> None:
    client = _Client()
    writer = BigQuerySnapshotWriter(
        project="unit-project",
        snapshot_field="snapshot_at",
        client=client,
    )

    affected = writer.write(
        [
            {
                "id": "one",
                "snapshot_at": "2026-07-29T12:00:00Z",
                "label": "active",
            }
        ],
        _target(),
    )

    assert affected == 1
    assert "PARTITION BY DATE(`snapshot_at`)" in client.queries[0]
    insert = client.queries[1]
    assert insert.startswith("INSERT INTO")
    assert "WHERE NOT EXISTS" in insert
    assert "IS NOT DISTINCT FROM" in insert
    assert "PARTITION BY TO_JSON_STRING(source)" in insert
    assert "SELECT *" not in insert
    assert client.deleted == [client.destination]


def test_snapshot_writer_rejects_missing_or_null_snapshot_value() -> None:
    writer = BigQuerySnapshotWriter(
        project="unit-project",
        snapshot_field="snapshot_at",
        client=_Client(),
    )

    with pytest.raises(BigQueryWriteError, match="absent"):
        writer.write([{"id": "one"}], _target())
    with pytest.raises(BigQueryWriteError, match="null snapshot"):
        writer.write([{"id": "one", "snapshot_at": None}], _target())


def test_scd2_writer_builds_transactional_change_history() -> None:
    client = _Client()
    writer = BigQueryScd2Writer(project="unit-project", client=client)

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
    create = client.queries[0]
    assert "valid_from" in create
    assert "valid_to" in create
    assert "is_current" in create
    history = client.queries[1]
    assert "CREATE TEMP TABLE changed" in history
    assert "IS DISTINCT FROM" in history
    assert "BEGIN TRANSACTION" in history
    assert "SET `valid_to` = effective_at, `is_current` = FALSE" in history
    assert "COMMIT TRANSACTION" in history
    assert "SELECT *" not in history
    assert client.deleted == [client.destination]


def test_scd2_writer_rejects_reserved_columns_and_missing_key() -> None:
    writer = BigQueryScd2Writer(project="unit-project", client=_Client())

    with pytest.raises(BigQueryWriteError, match="reserved column"):
        writer.write([{"id": "one", "valid_from": "user-data"}], _target())
    with pytest.raises(BigQueryWriteError, match="business-key"):
        writer.write(
            [{"id": "one"}],
            WriteTarget(project="unit-project", dataset="raw", table="snapshots"),
        )


@pytest.mark.parametrize(
    "writer",
    [
        BigQuerySnapshotWriter(
            project="unit-project",
            snapshot_field="snapshot_at",
            client=_Client(),
        ),
        BigQueryScd2Writer(project="unit-project", client=_Client()),
    ],
)
def test_new_writers_reject_project_mismatch(writer: WritePattern) -> None:
    target = WriteTarget(
        project="other-project",
        dataset="raw",
        table="example_widgets",
        business_key=("id",),
    )

    with pytest.raises(BigQueryWriteError, match="does not match"):
        writer.write(
            [{"id": "one", "snapshot_at": "2026-07-29T12:00:00Z"}],
            target,
        )
