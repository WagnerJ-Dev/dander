---
id: DANDER-32
title: Prove the hand-rolled enterprise ingestion path
status: complete
component: ingestion
epic: runtime
depends_on: [DANDER-20]
created: 2026-07-29
---

## Acceptance Criteria

- [x] A concrete Workday RaaS JSON source implements the shared `Source` interface without dlt.
- [x] Auth, HTTP transport, page-number pagination, response-envelope selection, and incremental
      cursor parameters are exercised with injected fakes.
- [x] Endpoint BigQuery type overrides execute and fail closed without leaking row values.
- [x] Discovery returns declarations only and never samples source rows.
- [x] Unknown endpoints, unsupported pagination, malformed envelopes, and non-mapping rows fail.
- [x] Public exports, documentation, strict typing, tests, and full checks pass.

## Review Log

Implemented a CLI-selectable `workday_raas` engine with an injected HTTP transport and sleeper.
Synthetic tests cover two-page extraction, OAuth/basic strategy application at the shared auth
seam, cursor/query parameters, declaration-only discovery, seven scalar cast types, bounded
exponential retry, and fail-closed malformed responses.
