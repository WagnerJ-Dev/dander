---
id: DANDER-57
title: Verify complete cost guard
status: in-code
component: python
epic: proof-release
depends_on: [DANDER-54]
created: 2026-07-31
---

## Context

Connectivity to the Billing API is not proof that Dander's budget and notification path exists.

## Acceptance Criteria

- [x] Exact budget, amount, project filter, thresholds, topic, trigger, function, identity, mode,
      and billing linkage are verified.
- [x] Empty, unrelated, and mismatched resources fail.
- [x] Routine proofs remain simulation-first.

## Design

Use read-only gcloud resource descriptions and sanitized comparisons against expected Terraform
outputs.

## Implementation Notes

Implemented in `DeploymentVerifier` with exact named-resource comparisons and simulation-first
defaults. A real billing-linked result remains unclaimed.

## Review Log
