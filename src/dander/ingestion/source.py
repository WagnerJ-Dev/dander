"""The ``Source`` abstraction — the common contract for BOTH ingestion paths.

Per the hybrid decision (see the Decision Log in ``steering/00-project-overview.md``): standard
REST sources are implemented on dlt; gnarly enterprise sources (Workday, NetSuite, Xactly) are
hand-rolled. Both implement ``Source``, so the writer, state, and orchestration layers never care
which path produced the records.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from typing import Any

from pydantic import BaseModel, Field


class Endpoint(BaseModel):
    """One retrievable entity within a source (loaded from the connector YAML)."""

    name: str
    path: str
    pagination: str = "none"
    incremental_cursor: str | None = None
    primary_key: list[str] = Field(default_factory=list)


class SourceConfig(BaseModel):
    """Declarative definition of a source system and its endpoints."""

    name: str
    base_url: str
    auth_strategy: str = Field(description="Registered AuthStrategy key, e.g. 'api_key_basic'")
    auth_ref: str = Field(description="Secret reference the AuthStrategy resolves (never the value)")
    endpoints: list[Endpoint] = Field(default_factory=list)


class Source(ABC):
    """Extracts records from one source system, endpoint by endpoint."""

    def __init__(self, config: SourceConfig) -> None:
        self.config = config

    @abstractmethod
    def discover(self) -> Mapping[str, Any]:
        """Return an inferred schema per endpoint (feeds type casting + the catalog spine)."""

    @abstractmethod
    def extract(self, endpoint: str, *, since: str | None = None) -> Iterator[Mapping[str, Any]]:
        """Yield records for ``endpoint``, optionally bounded by an incremental watermark ``since``."""
