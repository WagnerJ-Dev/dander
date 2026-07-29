"""Pipeline commit-order tests for DANDER-20."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from dander.ingestion.source import Endpoint, Source, SourceConfig
from dander.runtime import PipelineRunner
from dander.state import WatermarkStore
from dander.writer import WriteMode, WritePattern, WriteTarget

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping


class _Source(Source):
    def __init__(self, events: list[str]) -> None:
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

    def discover(self) -> Mapping[str, Any]:
        return {}

    def extract(self, endpoint: str, *, since: str | None = None) -> Iterator[Mapping[str, Any]]:
        assert endpoint == "widgets"
        assert since == "2026-01-01T00:00:00Z"
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


def test_runner_does_not_advance_cursor_when_write_fails() -> None:
    events: list[str] = []
    runner, watermarks = _runner(events, fail=True)

    with pytest.raises(RuntimeError, match="synthetic write failure"):
        runner.run()

    assert events == ["get", "extract", "write"]
    assert watermarks.committed is None
