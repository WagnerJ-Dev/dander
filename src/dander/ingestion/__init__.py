"""Ingestion module: source config models and the two extraction paths (dlt + hand-rolled)."""

from __future__ import annotations

from dander.ingestion.pagination import (
    CursorPagination,
    LinkHeaderPagination,
    NoPagination,
    OffsetPagination,
    PageNumberPagination,
    PaginationKind,
    PaginationStrategy,
)
from dander.ingestion.source import Endpoint, Source, SourceConfig

__all__ = [
    "CursorPagination",
    "Endpoint",
    "LinkHeaderPagination",
    "NoPagination",
    "OffsetPagination",
    "PageNumberPagination",
    "PaginationKind",
    "PaginationStrategy",
    "Source",
    "SourceConfig",
]
