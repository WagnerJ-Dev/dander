"""Ingestion module: source config models and the two extraction paths (dlt + hand-rolled)."""

from __future__ import annotations

from dander.ingestion.config import ConnectorConfigError, load_source_config
from dander.ingestion.dlt_backed import DltRestSource
from dander.ingestion.enterprise import (
    EnterpriseHttpClient,
    EnterpriseSource,
    EnterpriseSourceError,
    WorkdayRaasSource,
)
from dander.ingestion.pagination import (
    CursorPagination,
    LinkHeaderPagination,
    NoPagination,
    OffsetPagination,
    PageNumberPagination,
    PaginationKind,
    PaginationStrategy,
)
from dander.ingestion.source import Endpoint, IngestionEngine, Source, SourceConfig

__all__ = [
    "CursorPagination",
    "ConnectorConfigError",
    "DltRestSource",
    "Endpoint",
    "EnterpriseHttpClient",
    "EnterpriseSource",
    "EnterpriseSourceError",
    "IngestionEngine",
    "LinkHeaderPagination",
    "NoPagination",
    "OffsetPagination",
    "PageNumberPagination",
    "PaginationKind",
    "PaginationStrategy",
    "Source",
    "SourceConfig",
    "WorkdayRaasSource",
    "load_source_config",
]
