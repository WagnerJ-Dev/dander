---
id: DANDER-62
title: Add manual live-proof workflow
status: in-code
component: docs
epic: proof-release
depends_on: [DANDER-52, DANDER-54, DANDER-55, DANDER-56, DANDER-57]
created: 2026-07-31
---

## Context

External proofs need one approval-gated, WIF-authenticated execution path with retained evidence.

## Acceptance Criteria

- [ ] Manual dispatch accepts project, connector, Storage Write, transforms, Dataplex, cost guard,
      and teardown inputs.
- [ ] Workflow uses WIF and runtime identities, never service-account JSON keys.
- [ ] Successful and partial runs upload a complete sanitized bundle.

## Design

Use a protected `live-proof` environment and fail-closed ordered steps with an always-run evidence
upload.

## Implementation Notes

Implemented `.github/workflows/live-proof.yml` with protected-environment WIF authentication,
manual proof inputs, fail-closed ordered steps, and always-uploaded finalized evidence. It still
requires repository environment configuration and an approved live run. The workflow installs its
locked runtime and Terraform explicitly, and exports the project alias into the evidence manifest.

## Review Log
