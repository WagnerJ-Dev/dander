---
id: DANDER-60
title: Prove hosted transforms and tests
status: in-code
component: python
epic: proof-release
depends_on: [DANDER-58]
created: 2026-07-31
---

## Context

The hosted transform tail needs a real model and incremental proof from authenticated source data.

## Acceptance Criteria

- [ ] `stg_hubspot__companies` builds in the hosted path.
- [ ] Meaningful not-null, unique, accepted-values, and safe relationship tests pass.
- [ ] An update changes only the intended row and evidence links the source run.

## Design

Add a narrow staging model YAML/SQL and run the existing transform runner after ingestion.

## Implementation Notes

Implemented in the hosted runtime toggle, HubSpot staging model, and
`scripts/live_proof/transforms.py`; the live Cloud Run proof is intentionally unclaimed.

## Review Log
