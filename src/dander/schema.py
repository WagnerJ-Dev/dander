"""Shared BigQuery schema vocabulary for connector and writer contracts."""

from __future__ import annotations

BIGQUERY_TYPE_ALIASES = {
    "BOOLEAN": "BOOL",
    "FLOAT": "FLOAT64",
    "INTEGER": "INT64",
    "STRUCT": "RECORD",
}
BIGQUERY_FIELD_TYPES = frozenset(
    {
        "BIGNUMERIC",
        "BOOL",
        "BYTES",
        "DATE",
        "DATETIME",
        "FLOAT64",
        "GEOGRAPHY",
        "INT64",
        "INTERVAL",
        "JSON",
        "NUMERIC",
        "RECORD",
        "STRING",
        "TIME",
        "TIMESTAMP",
    }
)
BIGQUERY_FIELD_MODES = frozenset({"NULLABLE", "REPEATED", "REQUIRED"})


def normalize_bigquery_type(value: str) -> str:
    """Return the canonical BigQuery type name for a supported alias."""
    normalized = value.upper()
    return BIGQUERY_TYPE_ALIASES.get(normalized, normalized)
