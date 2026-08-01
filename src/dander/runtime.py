"""Runtime orchestration for source extraction, idempotent loading, and cursor commits."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import batched
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from dander.state.run_history import RunHistoryStore, RunStatus
from dander.writer.base import WriteTarget

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

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
        batch_rows: int = 10_000,
    ) -> None:
        self._source = source
        self._writer = writer
        self._watermarks = watermarks
        self._project = project
        self._dataset = dataset
        self._resume_from_watermark = resume_from_watermark
        self._history = history
        if isinstance(batch_rows, bool) or not 1 <= batch_rows <= 100_000:
            raise ValueError("batch_rows must be an integer from 1 to 100000")
        self._batch_rows = batch_rows

    def run(self, *, run_id: str | None = None) -> PipelineRunResult:
        """Run every configured endpoint and commit each cursor after its successful write."""
        run_id = run_id or uuid4().hex
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
        target = WriteTarget(
            project=self._project,
            dataset=self._dataset,
            table=f"{source_name}_{endpoint.name}",
            business_key=tuple(endpoint.primary_key),
        )
        observation = _RecordObservation(endpoint)
        records = _observed_records(
            self._source.extract(endpoint.name, since=cursor),
            observation,
        )
        if self._writer.supports_batched_writes:
            affected = self._write_batched(
                records,
                endpoint=endpoint,
                target=target,
                run_id=run_id,
            )
        elif self._writer.accepts_streaming_input:
            affected = self._writer.write(records, target)
        else:
            affected = self._writer.write(list(records), target)
        if observation.extracted and observation.maximum_cursor is not None:
            self._watermarks.set(source_name, endpoint.name, observation.maximum_cursor)

        _LOGGER.info(
            "endpoint_finished",
            extra={
                "affected": affected,
                "dander_event": "endpoint_finished",
                "endpoint": endpoint.name,
                "extracted": observation.extracted,
                "run_id": run_id,
                "source": source_name,
            },
        )
        return EndpointRunResult(
            endpoint=endpoint.name,
            extracted=observation.extracted,
            affected=affected,
            committed_cursor=observation.maximum_cursor if observation.extracted else None,
        )

    def _write_batched(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        endpoint: Endpoint,
        target: WriteTarget,
        run_id: str,
    ) -> int:
        affected = 0
        wrote_batch = False
        for batch_index, record_batch in enumerate(
            batched(records, self._batch_rows),
            start=1,
        ):
            wrote_batch = True
            batch_affected = self._writer.write(record_batch, target)
            affected += batch_affected
            _LOGGER.info(
                "batch_finished",
                extra={
                    "affected": batch_affected,
                    "batch": batch_index,
                    "dander_event": "batch_finished",
                    "endpoint": endpoint.name,
                    "extracted": len(record_batch),
                    "run_id": run_id,
                    "source": self._source.config.name,
                },
            )
        if not wrote_batch:
            affected = self._writer.write((), target)
        return affected


class _RecordObservation:
    """Track safe endpoint aggregates while records flow through bounded writes."""

    def __init__(self, endpoint: Endpoint) -> None:
        self._endpoint = endpoint
        self.extracted = 0
        self.maximum_cursor: str | None = None

    def observe(self, record: Mapping[str, Any]) -> None:
        index = self.extracted
        self.extracted += 1
        cursor_field = self._endpoint.incremental_cursor
        if cursor_field is None:
            return
        value = record.get(cursor_field)
        if value is None or isinstance(value, (dict, list)):
            raise CursorValueError(
                f"Endpoint {self._endpoint.name!r} record {index} has no scalar "
                f"cursor field {cursor_field!r}"
            )
        cursor = str(value)
        self.maximum_cursor = (
            max(self.maximum_cursor, cursor) if self.maximum_cursor is not None else cursor
        )


def _observed_records(
    records: Iterable[Mapping[str, Any]],
    observation: _RecordObservation,
) -> Iterable[Mapping[str, Any]]:
    for record in records:
        observation.observe(record)
        yield record
