---
id: DANDER-53
title: Add stage-zero bootstrap identity
status: in-code
component: terraform
epic: proof-release
depends_on: [DANDER-48, DANDER-49]
created: 2026-07-31
---

## Context

The main Terraform root cannot create and impersonate its own first-use identity in one apply.

## Acceptance Criteria

- [x] A small administrative root creates the state bucket, bootstrap service account, required
      provisioning roles, and approved caller impersonation binding.
- [x] Stage zero has separate local bootstrap state and no runtime resources.
- [x] Tests reject unsafe or missing administrator and bucket configuration.

## Design

`infra/bootstrap-admin` uses an explicitly approved administrative caller and creates only the
preconditions required by the main platform root.

## Implementation Notes

Implemented in `infra/bootstrap-admin` and `dander init-admin-plan/apply`; it also creates the
empty Artifact Registry repository required to push the first immutable runtime image, but no
Cloud Run, Scheduler, dataset, or secret workload is created. Live apply remains a separate
operational proof.

## Review Log
