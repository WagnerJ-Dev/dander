---
id: DANDER-28
title: Bootstrap the complete optional runtime stack
status: complete
component: terraform
epic: bootstrap
depends_on: [DANDER-23, DANDER-25]
created: 2026-07-29
---

## Context

The upstream architecture says `dander init` provisions BigQuery, Secret Manager, least-privilege
identities/WIF, and Cloud Run. Terraform now contains BigQuery and the scheduled public job, but the
CLI passes only a project id and cannot opt into that runtime. Secret containers and keyless GitHub
deployment identity are still absent.

## Acceptance Criteria

- [x] Terraform can create named Secret Manager containers without secret versions or values and
      grant the scheduled runtime access only to those named secrets.
- [x] Terraform can create a GitHub OIDC workload identity pool/provider and a narrow deployment
      service account without any service-account key.
- [x] The GitHub principal is repository/ref constrained and can impersonate only the deployment
      account; the deployer can push images, update Cloud Run, and act as only named runtime accounts.
- [x] `dander init` safely validates and passes region, BigQuery location, optional runtime image,
      billing account, paused schedule, secret ids, and optional GitHub repository/ref variables.
- [x] Runtime enablement requires an immutable image digest and billing account; plans remain the
      default and applies still require the exact saved plan plus interactive confirmation.
- [x] Existing deployed infrastructure produces a no-change plan when new optional modules are off.
- [x] Documentation, handoff, linting, formatting, strict typing, Terraform validation, and the
      full test suite pass.

## Design

Keep both modules disabled by empty input so existing state is migration-safe. Secret Manager owns
containers and IAM only, never versions. WIF is for external GitHub deployment; Cloud Run continues
to use its attached Google service account. The bootstrap accepts only direct subprocess arguments,
never shell interpolation.

## Review Log

Implemented as opt-in local modules with no secret-value resources or service-account keys. The
existing sandbox state produced a literal `No changes` plan with both additions disabled. The WIF
deployer's Artifact Registry grant is repository-scoped; its broader Cloud Run developer role is
paired with `iam.serviceAccountUser` only on Dander's two runtime identities.
