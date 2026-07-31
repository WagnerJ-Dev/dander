---
id: DANDER-31
title: Execute watermark-bounded incremental SQL models
status: complete
component: transform
epic: runtime
depends_on: [DANDER-26, DANDER-30]
created: 2026-07-29
---

## Acceptance Criteria

- [x] Incremental model metadata requires declared `unique_key` and `incremental_cursor` columns.
- [x] Compilation creates the target if absent, bounds source rows at the target max cursor,
      deduplicates business keys by latest cursor, and performs an explicit-column `MERGE`.
- [x] Mutable columns update and unseen keys insert; rerunning the same boundary is idempotent.
- [x] Invalid metadata and unsafe/missing columns fail before queries.
- [x] Existing view/table builds and generic tests remain unchanged.
- [x] Documentation, strict typing, tests, and full checks pass.

## Review Log

Implemented as one BigQuery multi-statement build: create-if-absent followed by a watermark-bounded,
per-key deduplicated `MERGE`. Metadata validation resolves all key/cursor names against declared
safe columns before compilation or query submission.
