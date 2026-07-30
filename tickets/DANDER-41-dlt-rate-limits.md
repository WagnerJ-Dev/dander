---
id: DANDER-41
title: Enforce per-source rate limits on dlt REST connectors
status: complete
component: ingestion
epic: runtime
depends_on: [DANDER-13, DANDER-20]
created: 2026-07-29
---

## Acceptance Criteria

- [x] A configured dlt source uses token-bucket request pacing and its declared burst.
- [x] Retryable read failures use the configured fixed or exponential backoff.
- [x] Retry attempts remain bounded and emit metadata-only audit logs.
- [x] Mutating HTTP methods are never retried automatically.
- [x] Retry-After is honored without permitting an unbounded sleep.
- [x] Sources without a rate-limit declaration retain dlt's default session behavior.
- [x] Strict typing and focused tests pass.
