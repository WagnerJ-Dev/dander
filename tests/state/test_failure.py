"""Operator-safe run failure classification."""

from __future__ import annotations

from dataclasses import dataclass

from dander.state import RunStage, classify_failure


@dataclass
class _Response:
    status_code: int


class _HttpError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.response = _Response(status_code)


def test_failure_classifier_uses_http_status_without_persisting_exception_text() -> None:
    error = RuntimeError("wrapper with token=top-secret")
    error.__cause__ = _HttpError(401, "private-key=also-secret")

    failure = classify_failure(error, stage=RunStage.INGEST, run_id="safe-run")

    assert failure.code == "authentication_failed"
    assert "top-secret" not in failure.summary
    assert "also-secret" not in failure.summary
    assert len(failure.summary) <= 512


def test_unknown_failure_is_stage_specific_and_points_to_run_logs() -> None:
    failure = classify_failure(
        RuntimeError("customer payload must never persist"),
        stage=RunStage.METADATA,
        run_id="run-123",
    )

    assert failure.code == "catalog_failed"
    assert failure.summary == (
        "Metadata or catalog publication failed. Inspect logs for run run-123."
    )
    assert "customer payload" not in failure.summary
