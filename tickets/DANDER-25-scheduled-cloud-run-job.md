---
id: DANDER-25
title: Scheduled public ingestion on Cloud Run Jobs
status: done
component: terraform
epic: runtime
depends_on: [DANDER-22, DANDER-24]
created: 2026-07-29
---

## Context

The public Greenhouse connector runs locally through the guarded BigQuery path. The next vertical
slice packages that exact command as a scheduled Cloud Run Job without default service accounts,
always-on compute, private credentials, or unbounded image retention.

## Acceptance Criteria

- [x] A pinned, non-root container runs the public guarded connector with locked dependencies.
- [x] Terraform provisions a dedicated runtime identity, scheduler identity, Artifact Registry
      cleanup, Cloud Run Job, and paused-first daily schedule.
- [x] Runtime access is limited to BigQuery jobs, raw-dataset writes, Pub/Sub guard inspection,
      and read-only billing-budget inspection.
- [x] The image builds successfully and the container CLI smoke test passes.
- [x] A manual Cloud Run execution succeeds before the daily schedule is enabled.
- [x] Terraform ends with a no-change plan; the billing guard and table integrity remain healthy.
- [x] Documentation, handoff, tests, linting, typing, and Terraform validation pass.

## Review Log

PASS — the direct and scheduler-authenticated executions each wrote 21 distinct public jobs,
Terraform reported no changes after enablement, the container uses an immutable digest and
dedicated non-default identity, and all repository checks passed.
