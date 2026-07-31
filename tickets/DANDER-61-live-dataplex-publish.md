---
id: DANDER-61
title: Publish and read back Dataplex metadata
status: in-code
component: python
epic: proof-release
depends_on: [DANDER-60, DANDER-54]
created: 2026-07-31
---

## Context

Local metadata compilation exists; one real aspect must be published and compared by read-back.

## Acceptance Criteria

- [ ] The HubSpot staging model aspect is published without deleting unrelated metadata.
- [ ] Read-back, idempotent republish, and one-field update are verified.
- [ ] Evidence contains only entry/aspect identifiers and normalized content hashes.

## Design

Reuse `MetadataSpine` and `DataplexCatalogPublisher`, adding read-back and normalized comparison.

## Implementation Notes

Implemented read-back normalization in `DataplexCatalogPublisher` and a sanitized live-proof
script. No Dataplex mutation has been run from this branch.

## Review Log
