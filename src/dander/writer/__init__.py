"""BigQuery writer module: explicit, idempotent write patterns."""

from dander.writer.base import SchemaEvolution, WriteField, WriteMode, WritePattern, WriteTarget
from dander.writer.bigquery import (
    BigQueryIncrementalWriter,
    BigQueryReplaceWriter,
    BigQueryScd1Writer,
    BigQueryScd2Writer,
    BigQuerySnapshotWriter,
    BigQueryWriteError,
)

__all__ = [
    "BigQueryIncrementalWriter",
    "BigQueryReplaceWriter",
    "BigQueryScd1Writer",
    "BigQueryScd2Writer",
    "BigQuerySnapshotWriter",
    "BigQueryWriteError",
    "SchemaEvolution",
    "WriteField",
    "WriteMode",
    "WritePattern",
    "WriteTarget",
]
