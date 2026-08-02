# BigQuery write patterns

All patterns stage JSON rows in a unique table, name columns explicitly, validate identifiers and
shape before mutation, and delete staging in a `finally` block.

| Writer | Contract |
|---|---|
| `BigQueryScd1Writer` | Last-record-wins batch deduplication and business-key `MERGE`. |
| `BigQueryIncrementalWriter` | Non-null cursor validation plus the same idempotent key merge; extraction owns the watermark bound. |
| `BigQuerySnapshotWriter` | Date-partitioned append with exact-row rerun suppression, including duplicate rows in one batch. |
| `BigQueryScd2Writer` | Transactionally closes changed current rows and inserts versions with `valid_from`, `valid_to`, and `is_current`. |
| `BigQueryReplaceWriter` | Bounded run-scoped staging followed by atomic sandbox replacement. |
| `BigQueryStorageScd1Writer` | Atomic pending-stream ingestion into staging, followed by keyed `MERGE`. |
| `BigQueryStorageIncrementalWriter` | Pending-stream staging plus cursor validation and keyed `MERGE`. |

SCD2 reserves `valid_from`, `valid_to`, and `is_current`. Snapshot input must contain the
configured non-null timestamp/date partition field. Hosted SCD1 receives bounded endpoint batches;
sandbox replace loads bounded batches into expiring staging and publishes only after extraction
completes. Other writers validate their logical batch once, then bound individual BigQuery load
requests with `max_batch_rows`. Strict schema behavior is the default. Hosted SCD1 validates the
complete declared schema against BigQuery and may add only missing top-level nullable fields; it
never changes types, modes, nested fields, or deployed-only columns. Empty SCD1 and replace writes
can bootstrap a target directly from the declaration. Storage Write API selection is explicit
through target `transport`: load jobs remain the low-latency-insensitive batch default, while
`storage_write` uses offset-checked protobuf appends to a pending stream, finalizes it, commits
atomically, and then merges from staging. The Python path currently accepts BOOL, BYTES, FLOAT64,
INT64, and STRING schemas; other types fail before creating staging.

Hosted DML finalizers carry the active run's fencing token. SCD1, incremental, snapshot, SCD2, and
Storage Write merge/insert transactions conditionally DML-touch the matching lease row before
mutating the target and abort when the pipeline ID, run ID, token, or live expiry no longer match.
Each hosted pipeline uses a deterministic lease table so BigQuery's table-wide mutation conflicts
cannot couple unrelated pipelines.
The lease check is in the target transaction, not a preceding read. Permanent-table DDL remains
outside BigQuery transactions. `BigQueryReplaceWriter` rejects a cloud fence explicitly because
permanent table replacement cannot provide the same transactional fencing guarantee; replace is
the sandbox/local v0.1 path.
