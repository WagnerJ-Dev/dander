"""Hand-rolled extractor base — for enterprise sources dlt's generics can't express.

Workday RaaS, NetSuite OAuth1 TBA, Xactly: auth models, pagination, and data shapes that need full
control of the request cycle. Built on ``httpx`` + ``tenacity`` (bounded backoff). Each concrete
enterprise source subclasses this. See the auth strategy table in ``steering/01-security.md``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from dander.ingestion.source import Source


class EnterpriseSource(Source):
    """Base for bespoke enterprise extractors that fully control the request cycle."""

    def discover(self) -> Mapping[str, Any]:
        raise NotImplementedError("DANDER: infer schema for the concrete enterprise source")

    def extract(self, endpoint: str, *, since: str | None = None) -> Iterator[Mapping[str, Any]]:
        raise NotImplementedError("DANDER: implement auth + pagination + extraction for this source")
