"""Watermark / control state — last successful cursor per (source, entity).

Enables idempotent restarts: a re-run resumes from the last committed cursor rather than
re-pulling or corrupting data. Backed by BigQuery or Firestore. See ``steering/02-engineering.md``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class WatermarkStore(ABC):
    """Persists the incremental cursor for each (source, entity) pair."""

    @abstractmethod
    def get(self, source: str, entity: str) -> str | None:
        """Return the last successful cursor value, or ``None`` if never run."""

    @abstractmethod
    def set(self, source: str, entity: str, cursor: str) -> None:
        """Persist ``cursor`` after a successful load (called only on commit)."""
