---
id: DANDER-30
title: Execute all declared BigQuery write patterns
status: complete
component: writer
epic: runtime
depends_on: [DANDER-16, DANDER-20]
created: 2026-07-29
---

## Context

`WriteMode` and target-node configuration promise SCD1, SCD2, snapshot, and incremental behavior,
but only SCD1 and full replacement execute. The mismatch makes valid pipeline configurations
non-runnable.

## Acceptance Criteria

- [x] Incremental writes require a non-null cursor and remain idempotent by merging business keys.
- [x] Snapshot writes are append-only and suppress exact rerun duplicates.
- [x] SCD2 writes close changed current rows and insert one new current version transactionally.
- [x] All writers validate project, identifiers, row shape, required keys, and reserved columns
      before network mutation.
- [x] SQL names columns explicitly, uses unique staging tables, and cleans staging on failure.
- [x] Public exports, documentation, strict typing, tests, and full checks pass.

## Review Log

Implemented all declared patterns as typed public writers. Snapshot exact comparisons and SCD2
change comparisons use `TO_JSON_STRING` so nested BigQuery values do not rely on scalar equality.
Target-node dispatch, bounded loading, and schema evolution remain explicitly separate.
