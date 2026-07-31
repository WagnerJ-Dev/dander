---
id: DANDER-59
title: Prove live Storage Write conformance
status: open
component: python
epic: proof-release
depends_on: [DANDER-55, DANDER-54]
created: 2026-07-31
---

## Context

The Storage Write implementation has offline coverage but needs a real pending-stream commit and
failure evidence.

## Acceptance Criteria

- [ ] Initial, retry, offset, update, schema, interruption, and commit scenarios are exercised.
- [ ] A shared writer contract covers fake, load-job, and Storage Write implementations.
- [ ] Watermark and content-hash evidence is sanitized.

## Design

Use a dedicated proof table and deterministic batches through the existing pending-stream writer.

## Implementation Notes

The live proof script exercises initial, exact-retry, update, nullable additive schema, invalid
schema, and simulated pre-commit interruption paths through the pending-stream writer. A real
Storage Write service run remains required for the acceptance criteria.

## Review Log
