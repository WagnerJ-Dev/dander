---
id: DANDER-39
title: Select BigQuery Storage Write API by workload
status: complete
component: writer
epic: runtime
depends_on: [DANDER-38]
created: 2026-07-29
---

## Acceptance Criteria

- [x] Target config explicitly selects load jobs or Storage Write transport.
- [x] Storage Write is limited to keyed SCD1/incremental workloads.
- [x] A pending stream appends bounded protobuf batches with monotonically increasing offsets.
- [x] The stream finalizes and commits atomically before staging is merged.
- [x] Reruns remain idempotent through business-key merge and unique staging cleanup.
- [x] Unsupported schemas and cursor violations fail before staging mutation.
- [x] Documentation, strict typing, tests, and full checks pass.
