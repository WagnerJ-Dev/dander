# BigQuery write patterns

All patterns stage JSON rows in a unique table, name columns explicitly, validate identifiers and
shape before mutation, and delete staging in a `finally` block.

| Writer | Contract |
|---|---|
| `BigQueryScd1Writer` | Last-record-wins batch deduplication and business-key `MERGE`. |
| `BigQueryIncrementalWriter` | Non-null cursor validation plus the same idempotent key merge; extraction owns the watermark bound. |
| `BigQuerySnapshotWriter` | Date-partitioned append with exact-row rerun suppression, including duplicate rows in one batch. |
| `BigQueryScd2Writer` | Transactionally closes changed current rows and inserts versions with `valid_from`, `valid_to`, and `is_current`. |
| `BigQueryReplaceWriter` | Direct `WRITE_TRUNCATE` load for no-DML sandbox operation. |

SCD2 reserves `valid_from`, `valid_to`, and `is_current`. Snapshot input must contain the
configured non-null timestamp/date partition field. These writers hold and validate one endpoint
batch in memory; bounded chunk loading and controlled schema evolution remain separate work.
