---
id: DANDER-37
title: Bound BigQuery load-job request sizes
status: complete
component: writer
epic: runtime
depends_on: [DANDER-30, DANDER-33]
created: 2026-07-29
---

## Acceptance Criteria

- [x] Every concrete writer accepts a positive maximum rows per load request.
- [x] Target configuration exposes a bounded 1–100,000 row setting.
- [x] The first chunk truncates and later chunks append to one target/staging table.
- [x] Logical-batch validation and keyed deduplication happen before chunking.
- [x] Empty writes and staging cleanup retain their existing contracts.
- [x] Documentation, strict typing, tests, and full checks pass.
