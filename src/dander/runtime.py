"""Runtime orchestration for source extraction, idempotent loading, and cursor commits."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from dander.state.run_history import RunHistoryStore, RunStatus
from dander.writer.base import WriteTarget

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dander.ingestion.source import Endpoint, Source
    from dander.state.watermark import WatermarkStore
    from dander.writer.base import WritePattern

_LOGGER = logging.getLogger(__name__)


class CursorValueError(ValueError):
    """Raised when a cursor-enabled endpoint returns an unusable cursor."""


@dataclass(frozen=True)
class EndpointRunResult:
    """Non-sensitive execution summary for one endpoint."""

    endpoint: str
    extracted: int
    affected: int
    committed_cursor: str | None


@dataclass(frozen=True)
class PipelineRunResult:
    """Execution summary for one connector run."""

    run_id: str
    source: str
    endpoints: tuple[EndpointRunResult, ...]


class PipelineRunner:
    """Coordinate one configured source without depending on concrete providers."""

    def __init__(
        self,
        *,
        source: Source,
        writer: WritePattern,
        watermarks: WatermarkStore,
        project: str,
        dataset: str,
        resume_from_watermark: bool = True,
        history: RunHistoryStore | None = None,
    ) -> None:
        self._source = source
        self._writer = writer
        self._watermarks = watermarks
        self._project = project
        self._dataset = dataset
        self._resume_from_watermark = resume_from_watermark
        self._history = history

    def run(self) -> PipelineRunResult:
        """Run every configured endpoint and commit each cursor after its successful write."""
        run_id = uuid4().hex
        source_name = self._source.config.name
        _LOGGER.info(
            "pipeline_started",
            extra={"dander_event": "pipeline_started", "run_id": run_id, "source": source_name},
        )
        if self._history is not None:
            self._history.start(run_id, source_name)
        completed: list[EndpointRunResult] = []
        try:
            for endpoint in self._source.config.endpoints:
                completed.append(self._run_endpoint(endpoint, run_id))
        except Exception:
            try:
                self._finish_history(run_id, completed, succeeded=False)
            except Exception:
                _LOGGER.exception(
                    "run_history_finish_failed",
                    extra={
                        "dander_event": "run_history_finish_failed",
                        "run_id": run_id,
                        "source": source_name,
                    },
                )
            raise
        results = tuple(completed)
        self._finish_history(run_id, completed, succeeded=True)
        _LOGGER.info(
            "pipeline_finished",
            extra={"dander_event": "pipeline_finished", "run_id": run_id, "source": source_name},
        )
        return PipelineRunResult(run_id=run_id, source=source_name, endpoints=results)

    def _finish_history(
        self,
        run_id: str,
        completed: list[EndpointRunResult],
        *,
        succeeded: bool,
    ) -> None:
        if self._history is None:
            return
        self._history.finish(
            run_id,
            RunStatus.SUCCEEDED if succeeded else RunStatus.FAILED,
            endpoints=len(completed),
            extracted=sum(result.extracted for result in completed),
            affected=sum(result.affected for result in completed),
        )

    def _run_endpoint(self, endpoint: Endpoint, run_id: str) -> EndpointRunResult:
        source_name = self._source.config.name
        cursor = (
            self._watermarks.get(source_name, endpoint.name)
            if endpoint.incremental_cursor and self._resume_from_watermark
            else None
        )
        records = list(self._source.extract(endpoint.name, since=cursor))
        committed_cursor = _maximum_cursor(records, endpoint)
        target = WriteTarget(
            project=self._project,
            dataset=self._dataset,
            table=f"{source_name}_{endpoint.name}",
            business_key=tuple(endpoint.primary_key),
        )
        affected = self._writer.write(records, target)
        if records and committed_cursor is not None:
            self._watermarks.set(source_name, endpoint.name, committed_cursor)

        _LOGGER.info(
            "endpoint_finished",
            extra={
                "affected": affected,
                "dander_event": "endpoint_finished",
                "endpoint": endpoint.name,
                "extracted": len(records),
                "run_id": run_id,
                "source": source_name,
            },
        )
        return EndpointRunResult(
            endpoint=endpoint.name,
            extracted=len(records),
            affected=affected,
            committed_cursor=committed_cursor if records else None,
        )


def _maximum_cursor(
    records: list[Mapping[str, Any]],
    endpoint: Endpoint,
) -> str | None:
    cursor_field = endpoint.incremental_cursor
    if cursor_field is None or not records:
        return None

    cursor_values: list[str] = []
    for index, record in enumerate(records):
        value = record.get(cursor_field)
        if value is None or isinstance(value, (dict, list)):
            raise CursorValueError(
                f"Endpoint {endpoint.name!r} record {index} has no scalar "
                f"cursor field {cursor_field!r}"
            )
        cursor_values.append(str(value))
    return max(cursor_values)
