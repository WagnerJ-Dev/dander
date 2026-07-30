---
id: DANDER-38
title: Add controlled BigQuery schema evolution
status: complete
component: writer
epic: runtime
depends_on: [DANDER-37]
created: 2026-07-29
---

## Acceptance Criteria

- [x] Strict schema behavior remains the default.
- [x] Target-node fields supply an explicit writer schema.
- [x] Additive mode adds declared scalar columns idempotently as nullable fields.
- [x] Existing columns are never dropped, renamed, made required, or type-mutated.
- [x] Missing declarations, duplicate names, and nested/unsupported types fail before loading.
- [x] SCD1, incremental, snapshot, and SCD2 apply the same policy.
- [x] Documentation, strict typing, tests, and full checks pass.
