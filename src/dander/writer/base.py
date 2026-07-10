"""BigQuery write patterns — explicit, idempotent load strategies.

dlt-sourced data may use dlt's own write dispositions; custom-sourced (enterprise) data and the
transform engine's materializations use these patterns. Every pattern is safely re-runnable. See
``steering/02-engineering.md`` (idempotency) and ``steering/languages/sql.md`` (write-pattern rules).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WriteMode(str, Enum):
    """Supported load strategies."""

    SCD1 = "scd1"                # MERGE on business key (overwrite in place)
    SCD2 = "scd2"                # versioned rows (valid_from / valid_to / is_current)
    SNAPSHOT = "snapshot"        # partitioned, append-only
    INCREMENTAL = "incremental"  # watermark-bounded append/merge


@dataclass(frozen=True)
class WriteTarget:
    """Fully-qualified BigQuery destination for a write."""

    project: str
    dataset: str
    table: str
    business_key: tuple[str, ...] = field(default_factory=tuple)


class WritePattern(ABC):
    """Loads a batch of records into a BigQuery target using one ``WriteMode``."""

    mode: WriteMode

    @abstractmethod
    def write(self, records: Iterable[Mapping[str, Any]], target: WriteTarget) -> int:
        """Write ``records`` to ``target`` idempotently; return the number of rows affected."""
