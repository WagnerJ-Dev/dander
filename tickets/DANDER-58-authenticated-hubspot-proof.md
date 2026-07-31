---
id: DANDER-58
title: Add authenticated HubSpot proof connector
status: in-code
component: python
epic: proof-release
depends_on: [DANDER-55, DANDER-54]
created: 2026-07-31
---

## Context

The owned HubSpot developer test account provides controlled invented records for an authenticated
REST proof without exposing public candidate data.

## Acceptance Criteria

- [x] Companies connector uses a Secret Manager-backed private-app bearer token.
- [ ] Initial, update, and no-change reruns prove SCD1 behavior and watermark safety.
- [ ] Evidence contains counts, IDs/hashes, and run metadata only.

## Design

Add a bearer auth strategy and narrow companies connector; keep contacts optional and out of the
first proof.

## Implementation Notes

Implemented in `connectors/hubspot_test.yaml`, `ApiKeyBearer`, the staging model, and
`scripts/live_proof/hubspot.py`; live execution still requires the sandbox private-app token.

## Review Log
