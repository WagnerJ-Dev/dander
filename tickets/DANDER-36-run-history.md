---
id: DANDER-36
title: Persist operational pipeline run history
status: complete
component: state
epic: runtime
depends_on: [DANDER-20]
created: 2026-07-29
---

## Acceptance Criteria

- [x] Every CLI pipeline run records running then succeeded/failed status.
- [x] Terminal records contain only endpoint, extracted, and affected aggregates.
- [x] Failures retain aggregates for completed endpoints and never store exception text or rows.
- [x] BigQuery uses parameterized DML; sandbox mode stores history in the existing SQLite file.
- [x] History remains an optional injected interface for library callers.
- [x] Documentation, strict typing, tests, and full checks pass.
