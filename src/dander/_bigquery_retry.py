"""Narrow retry support for BigQuery transaction contention."""

from __future__ import annotations

import logging
import random
from time import sleep
from typing import TYPE_CHECKING, Protocol

from google.api_core.exceptions import BadRequest

if TYPE_CHECKING:
    from collections.abc import Callable

_LOGGER = logging.getLogger(__name__)
_CONCURRENT_UPDATE = "transaction is aborted due to concurrent update against table"
_MAX_ATTEMPTS = 5
_BASE_DELAY_SECONDS = 0.25


class _Job(Protocol):
    def result(self) -> object:
        """Wait for the submitted BigQuery job."""


def run_mutation_with_retry[JobT: _Job](submit: Callable[[], JobT]) -> JobT:
    """Run a mutation, retrying only BigQuery's concurrent-update transaction abort."""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            job = submit()
            job.result()
            return job
        except BadRequest as error:
            if _CONCURRENT_UPDATE not in str(error).lower() or attempt == _MAX_ATTEMPTS:
                raise
            delay = (_BASE_DELAY_SECONDS * (2 ** (attempt - 1))) + random.uniform(
                0,
                _BASE_DELAY_SECONDS,
            )
            _LOGGER.warning(
                "BigQuery transaction contention; retrying mutation in %.2fs (attempt %d/%d)",
                delay,
                attempt + 1,
                _MAX_ATTEMPTS,
            )
            sleep(delay)
    raise AssertionError("BigQuery mutation retry loop exited unexpectedly")
