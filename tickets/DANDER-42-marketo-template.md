---
id: DANDER-42
title: Add a Marketo standard REST connector template
status: complete
component: ingestion
epic: connectors
depends_on: [DANDER-20, DANDER-41]
created: 2026-07-29
---

## Acceptance Criteria

- [x] The template contains only tenant placeholders and secret references.
- [x] OAuth supports Marketo's documented client-credential query placement.
- [x] API requests use the existing bearer-header adapter and token cache.
- [x] The read-only Programs endpoint uses dlt offset pagination and response selection.
- [x] The template declares Marketo's documented five-request-per-second instance limit.
- [x] Configuration and request-shape behavior are proven without tenant access.
