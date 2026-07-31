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
| `BigQueryStorageScd1Writer` | Atomic pending-stream ingestion into staging, followed by keyed `MERGE`. |
| `BigQueryStorageIncrementalWriter` | Pending-stream staging plus cursor validation and keyed `MERGE`. |

SCD2 reserves `valid_from`, `valid_to`, and `is_current`. Snapshot input must contain the
configured non-null timestamp/date partition field. Writers validate the logical endpoint batch
once, then bound each BigQuery load request with `max_batch_rows` (truncate first, append
thereafter). Strict schema behavior is the default. An opt-in additive mode issues only
`ADD COLUMN IF NOT EXISTS` for the target's declared scalar fields; it never changes types, modes,
or existing columns and rejects nested/unknown declarations before loading. Storage Write API
selection is explicit through target `transport`: load jobs remain the low-latency-insensitive
batch default, while `storage_write` uses offset-checked protobuf appends to a pending stream,
finalizes it, commits atomically, and then merges from staging. The Python path currently accepts
BOOL, BYTES, FLOAT64, INT64, and STRING schemas; other types fail before creating staging.
