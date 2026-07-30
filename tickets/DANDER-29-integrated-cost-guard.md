---
id: DANDER-29
title: Integrate the simulation-first cost guard into bootstrap
status: complete
component: terraform
epic: bootstrap
depends_on: [DANDER-23, DANDER-28]
created: 2026-07-29
---

## Context

The budget verifier and kill-switch handler exist, but new projects still require manual Pub/Sub,
budget, function, and IAM setup. That leaves the hosted runtime bootstrap incomplete.

## Acceptance Criteria

- [x] Terraform can package and deploy the existing Python handler as a Pub/Sub-triggered Gen 2
      Cloud Run function using the existing remote-state bucket for source storage.
- [x] Terraform creates a project-scoped USD budget no greater than $5 with 80% and 100%
      current-spend thresholds and all-update Pub/Sub notifications.
- [x] The function identity has only the project/billing permissions required to inspect and unlink
      the target project.
- [x] Simulation is the default; live detachment requires an explicit CLI option and remains
      subject to saved-plan review plus confirmation.
- [x] Cost-guard deployment is off by default and produces no migration drift.
- [x] Documentation clearly states that budget delivery is delayed, not a hard cap, and deploying
      the function uses billable services.
- [x] Full checks and both disabled/opt-in Terraform plans pass.

## Review Log

The disabled module produced a literal no-change plan against the live sandbox. The opt-in,
simulation plan produced 23 additions, no changes, and no destroys. It was intentionally not
applied because Cloud Run function deployment is billable and the existing sandbox already has
manually configured budget resources that would first need importing.
