"""Narrow BigQuery concurrent-update retry behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from google.api_core.exceptions import BadRequest

from dander import _bigquery_retry

if TYPE_CHECKING:
    from pytest import MonkeyPatch


class _Job:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error

    def result(self) -> object:
        if self._error is not None:
            raise self._error
        return self


def _concurrent_update_error() -> BadRequest:
    return BadRequest(
        "Transaction is aborted due to concurrent update against table unit.meta._dander_leases"
    )


def test_concurrent_update_transaction_is_resubmitted(monkeypatch: MonkeyPatch) -> None:
    success = _Job()
    jobs = [_Job(_concurrent_update_error()), success]
    delays: list[float] = []
    monkeypatch.setattr(_bigquery_retry.random, "uniform", lambda _start, _end: 0.0)
    monkeypatch.setattr(_bigquery_retry, "sleep", delays.append)

    result = _bigquery_retry.run_mutation_with_retry(lambda: jobs.pop(0))

    assert result is success
    assert delays == [0.25]


def test_unrelated_bad_request_is_not_retried(monkeypatch: MonkeyPatch) -> None:
    submissions = 0

    def submit() -> _Job:
        nonlocal submissions
        submissions += 1
        return _Job(BadRequest("Access Denied"))

    monkeypatch.setattr(
        _bigquery_retry,
        "sleep",
        lambda _delay: pytest.fail("unrelated error must not sleep"),
    )

    with pytest.raises(BadRequest, match="Access Denied"):
        _bigquery_retry.run_mutation_with_retry(submit)

    assert submissions == 1


def test_concurrent_update_retry_is_bounded(monkeypatch: MonkeyPatch) -> None:
    submissions = 0
    delays: list[float] = []

    def submit() -> _Job:
        nonlocal submissions
        submissions += 1
        return _Job(_concurrent_update_error())

    monkeypatch.setattr(_bigquery_retry.random, "uniform", lambda _start, _end: 0.0)
    monkeypatch.setattr(_bigquery_retry, "sleep", delays.append)

    with pytest.raises(BadRequest, match="concurrent update"):
        _bigquery_retry.run_mutation_with_retry(submit)

    assert submissions == 5
    assert delays == [0.25, 0.5, 1.0, 2.0]
