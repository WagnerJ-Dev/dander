"""Pipeline commit-order tests for DANDER-20."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from dander.ingestion.source import Endpoint, RawField, Source, SourceConfig
from dander.runtime import PipelineRunner, RawSchemaError
from dander.state import RunHistoryStore, RunStage, RunStatus, WatermarkStore
from dander.writer import WriteMode, WritePattern, WriteTarget

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping


class _Source(Source):
    def __init__(
        self,
        events: list[str],
        *,
        expected_since: str | None = "2026-01-01T00:00:00Z",
    ) -> None:
        super().__init__(
            SourceConfig(
                name="example",
                base_url="https://example.test",
                auth_strategy="api_key_basic",
                auth_ref="DANDER_TEST_REFERENCE",
                endpoints=[
                    Endpoint(
                        name="widgets",
                        path="/widgets",
                        incremental_cursor="updated_at",
                        primary_key=["id"],
                    )
                ],
            )
        )
        self._events = events
        self._expected_since = expected_since

    def discover(self) -> Mapping[str, Any]:
        return {}

    def extract(self, endpoint: str, *, since: str | None = None) -> Iterator[Mapping[str, Any]]:
        assert endpoint == "widgets"
        assert since == self._expected_since
        self._events.append("extract")
        yield {"id": "one", "updated_at": "2026-01-02T00:00:00Z"}
        yield {"id": "two", "updated_at": "2026-01-03T00:00:00Z"}


class _Writer(WritePattern):
    mode = WriteMode.SCD1

    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        self._events = events
        self._fail = fail

    def write(self, records: Iterable[Mapping[str, Any]], target: WriteTarget) -> int:
        assert target.table == "example_widgets"
        assert list(records)
        self._events.append("write")
        if self._fail:
            raise RuntimeError("synthetic write failure")
        return 2


class _BatchedWriter(WritePattern):
    mode = WriteMode.SCD1
    supports_batched_writes = True

    def __init__(self, *, fail_batch: int | None = None) -> None:
        self.batches: list[list[dict[str, Any]]] = []
        self.state: dict[str, dict[str, Any]] = {}
        self._fail_batch = fail_batch

    def write(self, records: Iterable[Mapping[str, Any]], target: WriteTarget) -> int:
        assert target.table == "example_widgets"
        batch = [dict(record) for record in records]
        self.batches.append(batch)
        if self._fail_batch == len(self.batches):
            raise RuntimeError("synthetic batch failure")
        for record in batch:
            self.state[str(record["id"])] = record
        return len(batch)


class _DeclaredSource(Source):
    def __init__(self, records: list[Mapping[str, Any]]) -> None:
        super().__init__(
            SourceConfig(
                name="declared",
                base_url="https://example.test",
                auth_strategy="none",
                endpoints=[
                    Endpoint(
                        name="companies",
                        path="/companies",
                        primary_key=["id"],
                        raw_schema=[
                            RawField(name="id", data_type="INT64", mode="REQUIRED"),
                            RawField(
                                name="properties",
                                data_type="RECORD",
                                fields=[
                                    RawField(name="name", data_type="STRING"),
                                    RawField(name="active", data_type="BOOL"),
                                ],
                            ),
                            RawField(name="tags", data_type="STRING", mode="REPEATED"),
                            RawField(
                                name="contacts",
                                data_type="RECORD",
                                mode="REPEATED",
                                fields=[
                                    RawField(name="email", data_type="STRING"),
                                    RawField(name="primary", data_type="BOOL"),
                                ],
                            ),
                            RawField(name="metadata", data_type="JSON"),
                        ],
                    )
                ],
            )
        )
        self._records = records

    def discover(self) -> Mapping[str, Any]:
        return {}

    def extract(self, endpoint: str, *, since: str | None = None) -> Iterator[Mapping[str, Any]]:
        assert endpoint == "companies"
        assert since is None
        yield from self._records


class _CapturingWriter(WritePattern):
    mode = WriteMode.SCD1
    supports_batched_writes = True

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.target: WriteTarget | None = None

    def write(self, records: Iterable[Mapping[str, Any]], target: WriteTarget) -> int:
        self.rows.extend(dict(record) for record in records)
        self.target = target
        return len(self.rows)


class _Watermarks(WatermarkStore):
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self.committed: str | None = None

    def get(self, source: str, entity: str) -> str | None:
        assert (source, entity) == ("example", "widgets")
        self._events.append("get")
        return "2026-01-01T00:00:00Z"

    def set(self, source: str, entity: str, cursor: str) -> None:
        assert (source, entity) == ("example", "widgets")
        self._events.append("set")
        self.committed = cursor


class _History(RunHistoryStore):
    def __init__(self) -> None:
        self.started: tuple[str, str] | None = None
        self.finished: tuple[str, RunStatus, int, int, int] | None = None

    def start(self, run_id: str, source: str, *, pipeline_id: str | None = None) -> None:
        assert pipeline_id is None
        self.started = (run_id, source)

    def finish(
        self,
        run_id: str,
        status: RunStatus,
        *,
        endpoints: int,
        extracted: int,
        affected: int,
        models: int = 0,
        assertions: int = 0,
        assets: int = 0,
        failure_stage: RunStage | None = None,
    ) -> None:
        assert (models, assertions, assets, failure_stage) == (0, 0, 0, None)
        self.finished = (run_id, status, endpoints, extracted, affected)


def _runner(events: list[str], *, fail: bool = False) -> tuple[PipelineRunner, _Watermarks]:
    watermarks = _Watermarks(events)
    return (
        PipelineRunner(
            source=_Source(events),
            writer=_Writer(events, fail=fail),
            watermarks=watermarks,
            project="unit-project",
            dataset="raw",
        ),
        watermarks,
    )


def test_runner_commits_maximum_cursor_after_write() -> None:
    events: list[str] = []
    runner, watermarks = _runner(events)

    result = runner.run()

    assert events == ["get", "extract", "write", "set"]
    assert watermarks.committed == "2026-01-03T00:00:00Z"
    assert result.endpoints[0].affected == 2


def test_runner_normalizes_sparse_nested_records_from_declared_schema() -> None:
    writer = _CapturingWriter()
    runner = PipelineRunner(
        source=_DeclaredSource(
            [
                {
                    "id": "42",
                    "properties": {"name": "Dander"},
                    "tags": None,
                    "contacts": [{"email": "proof@example.test"}],
                    "metadata": {"source": ["proof", 1]},
                }
            ]
        ),
        writer=writer,
        watermarks=_Watermarks([]),
        project="unit-project",
        dataset="raw",
    )

    result = runner.run()

    assert writer.rows == [
        {
            "id": 42,
            "properties": {"name": "Dander", "active": None},
            "tags": [],
            "contacts": [{"email": "proof@example.test", "primary": None}],
            "metadata": {"source": ["proof", 1]},
        }
    ]
    assert result.endpoints[0].extracted == 1
    assert writer.target is not None
    assert writer.target.schema[0].mode == "REQUIRED"
    assert writer.target.schema[1].fields[1].name == "active"


def test_runner_propagates_declared_schema_for_empty_endpoint() -> None:
    writer = _CapturingWriter()
    runner = PipelineRunner(
        source=_DeclaredSource([]),
        writer=writer,
        watermarks=_Watermarks([]),
        project="unit-project",
        dataset="raw",
    )

    result = runner.run()

    assert result.endpoints[0].extracted == 0
    assert writer.rows == []
    assert writer.target is not None
    assert [field.name for field in writer.target.schema] == [
        "id",
        "properties",
        "tags",
        "contacts",
        "metadata",
    ]


@pytest.mark.parametrize(
    ("record", "match"),
    [
        ({"id": 1, "unexpected": "x"}, r"record\[0\]\.unexpected"),
        (
            {"id": 1, "properties": {"unexpected": "x"}},
            r"record\[0\]\.properties\.unexpected",
        ),
        ({"properties": {}}, r"record\[0\]\.id"),
        ({"id": "not-an-integer"}, r"Invalid INT64 field at record\[0\]\.id"),
        ({"id": 1, "properties": "not-an-object"}, r"record\[0\]\.properties"),
        ({"id": 1, "tags": "not-a-list"}, r"record\[0\]\.tags"),
        ({"id": 1, "tags": [None]}, r"record\[0\]\.tags\[0\]"),
    ],
)
def test_runner_rejects_records_that_violate_declared_schema(
    record: Mapping[str, Any],
    match: str,
) -> None:
    writer = _CapturingWriter()
    runner = PipelineRunner(
        source=_DeclaredSource([record]),
        writer=writer,
        watermarks=_Watermarks([]),
        project="unit-project",
        dataset="raw",
    )

    with pytest.raises(RawSchemaError, match=match):
        runner.run()

    assert writer.rows == []


def test_raw_schema_failure_does_not_include_or_chain_source_value() -> None:
    source_value = "sensitive-not-an-integer"
    runner = PipelineRunner(
        source=_DeclaredSource([{"id": source_value}]),
        writer=_CapturingWriter(),
        watermarks=_Watermarks([]),
        project="unit-project",
        dataset="raw",
    )

    with pytest.raises(RawSchemaError) as raised:
        runner.run()

    assert source_value not in str(raised.value)
    assert raised.value.__cause__ is None


def test_direct_source_without_declared_schema_logs_deprecation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner, _ = _runner([])

    runner.run()

    assert "undeclared_raw_schema_deprecated" in caplog.messages


def test_runner_does_not_advance_cursor_when_write_fails() -> None:
    events: list[str] = []
    runner, watermarks = _runner(events, fail=True)

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        runner.run()

    assert events == ["get", "extract", "write"]
    assert watermarks.committed is None


def test_full_refresh_ignores_existing_cursor_but_records_observed_cursor() -> None:
    events: list[str] = []
    watermarks = _Watermarks(events)
    runner = PipelineRunner(
        source=_Source(events, expected_since=None),
        writer=_Writer(events),
        watermarks=watermarks,
        project="unit-project",
        dataset="raw",
        resume_from_watermark=False,
    )

    runner.run()

    assert events == ["extract", "write", "set"]
    assert watermarks.committed == "2026-01-03T00:00:00Z"


@pytest.mark.parametrize(
    ("fail", "status", "endpoints", "extracted", "affected"),
    [
        (False, RunStatus.SUCCEEDED, 1, 2, 2),
        (True, RunStatus.FAILED, 0, 0, 0),
    ],
)
def test_runner_records_non_sensitive_terminal_history(
    fail: bool,
    status: RunStatus,
    endpoints: int,
    extracted: int,
    affected: int,
) -> None:
    events: list[str] = []
    watermarks = _Watermarks(events)
    history = _History()
    runner = PipelineRunner(
        source=_Source(events),
        writer=_Writer(events, fail=fail),
        watermarks=watermarks,
        project="unit-project",
        dataset="raw",
        history=history,
    )

    if fail:
        with pytest.raises(RuntimeError, match="synthetic write failure"):
            runner.run()
    else:
        runner.run()

    assert history.started is not None
    run_id, source = history.started
    assert source == "example"
    assert history.finished == (run_id, status, endpoints, extracted, affected)


def test_scd1_runtime_writes_large_endpoint_in_bounded_batches() -> None:
    total = 100_003
    yielded = 0

    class _LargeSource(_Source):
        def extract(
            self,
            endpoint: str,
            *,
            since: str | None = None,
        ) -> Iterator[Mapping[str, Any]]:
            nonlocal yielded
            assert endpoint == "widgets"
            assert since == "2026-01-01T00:00:00Z"
            for index in range(total):
                yielded += 1
                yield {
                    "id": str(index),
                    "updated_at": f"{index:06d}",
                }

    class _ObservingWriter(_BatchedWriter):
        def __init__(self) -> None:
            super().__init__()
            self.first_write_yielded: int | None = None

        def write(self, records: Iterable[Mapping[str, Any]], target: WriteTarget) -> int:
            if self.first_write_yielded is None:
                self.first_write_yielded = yielded
            return super().write(records, target)

    writer = _ObservingWriter()
    watermarks = _Watermarks([])
    runner = PipelineRunner(
        source=_LargeSource([]),
        writer=writer,
        watermarks=watermarks,
        project="unit-project",
        dataset="raw",
        batch_rows=1_024,
    )

    result = runner.run()

    assert yielded == total
    assert writer.first_write_yielded == 1_024
    assert len(writer.batches) == 98
    assert max(map(len, writer.batches)) == 1_024
    assert len(writer.batches[-1]) == 675
    assert result.endpoints[0].extracted == total
    assert result.endpoints[0].affected == total
    assert watermarks.committed == "100002"


def test_scd1_cross_batch_duplicate_is_last_record_wins() -> None:
    events: list[str] = []

    class _DuplicateSource(_Source):
        def extract(
            self,
            endpoint: str,
            *,
            since: str | None = None,
        ) -> Iterator[Mapping[str, Any]]:
            assert endpoint == "widgets"
            assert since == "2026-01-01T00:00:00Z"
            yield {"id": "one", "updated_at": "2026-01-02T00:00:00Z"}
            yield {"id": "one", "updated_at": "2026-01-03T00:00:00Z"}

    writer = _BatchedWriter()
    runner = PipelineRunner(
        source=_DuplicateSource(events),
        writer=writer,
        watermarks=_Watermarks(events),
        project="unit-project",
        dataset="raw",
        batch_rows=1,
    )

    runner.run()

    assert writer.state["one"]["updated_at"] == "2026-01-03T00:00:00Z"


def test_scd1_does_not_advance_watermark_when_later_batch_fails() -> None:
    events: list[str] = []
    watermarks = _Watermarks(events)
    runner = PipelineRunner(
        source=_Source(events),
        writer=_BatchedWriter(fail_batch=2),
        watermarks=watermarks,
        project="unit-project",
        dataset="raw",
        batch_rows=1,
    )

    with pytest.raises(RuntimeError, match="synthetic batch failure"):
        runner.run()

    assert watermarks.committed is None


@pytest.mark.parametrize("batch_rows", [0, 100_001, True])
def test_runner_rejects_invalid_batch_rows(batch_rows: int) -> None:
    with pytest.raises(ValueError, match="batch_rows"):
        PipelineRunner(
            source=_Source([]),
            writer=_Writer([]),
            watermarks=_Watermarks([]),
            project="unit-project",
            dataset="raw",
            batch_rows=batch_rows,
        )
