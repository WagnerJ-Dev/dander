---
id: DANDER-55
title: Standardize sanitized evidence bundle
status: in-code
component: python
epic: proof-release
depends_on: [DANDER-52]
created: 2026-07-31
---

## Context

Every proof must emit consistent, sanitized evidence tied to its exact commit and image.

## Acceptance Criteria

- [x] Manifest and proof schemas cover success, failure, and skipped states.
- [x] Evidence excludes credentials, state payloads, source rows, and billing payloads.
- [x] Schema validation tests cover every proof file.

## Design

Use frozen typed evidence models and deterministic JSON serialization, with timestamps and run
identifiers supplied at the workflow boundary.

## Implementation Notes

Implemented in `src/dander/evidence`; `.github/workflows/live-proof.yml` and
`scripts/live_proof/finalize_evidence.py` complete the bundle after optional proof steps.

## Review Log
