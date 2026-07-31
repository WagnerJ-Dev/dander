---
id: DANDER-43
title: Add a deterministic local synthetic vendor API
status: complete
component: ingestion
epic: connectors
depends_on: [DANDER-20, DANDER-41]
created: 2026-07-30
---

## Acceptance Criteria

- [x] All records, names, identifiers, and failures are invented and local-only.
- [x] One endpoint exercises JSON cursor pagination and incremental updates.
- [x] One endpoint exercises RFC-style Link-header pagination.
- [x] Responses include duplicate business keys so writer idempotence can be tested safely.
- [x] The API returns deterministic 429 and 500 responses before succeeding.
- [x] The standard dlt adapter proves bounded retries and both pagination paths over real HTTP.
- [x] The server is runnable from the packaged development CLI without a credential.
