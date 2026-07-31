---
id: DANDER-44
title: Add real public Lever and Ashby job-board connectors
status: complete
component: ingestion
epic: connectors
depends_on: [DANDER-20, DANDER-41, DANDER-43]
created: 2026-07-30
---

## Acceptance Criteria

- [x] Greenhouse remains the documented primary real-world public demo.
- [x] Lever reads real published jobs without credentials and uses `skip`/`limit` pagination.
- [x] Ashby reads its real public job envelope without credentials.
- [x] Static query parameters are typed and reject credential-like names.
- [x] Offline tests pin both connector-to-dlt request contracts.
- [x] The synthetic API remains the only deliberate failure-injection source.
- [x] Candidate-like integration guidance uses fake records in an owned test account only.
