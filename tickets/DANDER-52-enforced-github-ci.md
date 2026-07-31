---
id: DANDER-52
title: Enforce GitHub CI
status: in-code
component: docs
epic: proof-release
depends_on: []
created: 2026-07-31
---

## Context

Live proofs must not begin while the current branch can merge without reproducible quality checks.

## Acceptance Criteria

- [x] Pull requests and pushes to `main` run Python, Terraform, container, and security checks.
- [x] Checks use no long-lived GCP credentials and have stable names for branch protection.
- [x] Local equivalents and required branch-protection settings are documented.

## Design

Use one credential-free workflow with separate jobs for Python, Terraform, container, and secret
scanning. Live WIF authentication belongs only to the later manual proof workflow.

## Implementation Notes

`.github/workflows/ci.yml` runs the four stable jobs; repository owners still need to require them
in branch protection. The container job also asserts the non-root UID and bundled HubSpot/model
proof assets before vulnerability scanning.

## Review Log
