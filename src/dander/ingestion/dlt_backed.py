"""dlt-backed source path — for standard REST APIs (Greenhouse, Marketo, …).

dlt handles the undifferentiated plumbing (pagination, retries, incremental cursors, schema
evolution, the BigQuery load). We adapt its ``rest_api`` source to our ``Source`` interface and
drive it from ``SourceConfig``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dander.ingestion.source import Source

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class DltRestSource(Source):
    """Wraps dlt's ``rest_api`` source behind the ``Source`` interface."""

    def discover(self) -> Mapping[str, Any]:
        raise NotImplementedError("DANDER: infer schema via dlt from a sample response")

    def extract(self, endpoint: str, *, since: str | None = None) -> Iterator[Mapping[str, Any]]:
        raise NotImplementedError(
            "DANDER: build a dlt rest_api source from SourceConfig and yield rows"
        )
