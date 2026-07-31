---
id: DANDER-51
title: Prove clean-project bootstrap
status: pending
component: operations
epic: bootstrap
created: 2026-07-30
---

## Acceptance criteria

- [ ] Run `dander init plan` from a clean billing-linked proof project with an approved bootstrap
      identity.
- [ ] Apply the reviewed plan with runtime and Scheduler paused.
- [ ] Attach `evidence/bootstrap-summary.json` from `dander verify deployment` to the proof run.
- [ ] Record teardown or an explicit retained-resource inventory before merge.

This ticket remains pending until a separately approved GCP proof run is performed; local tests and
Terraform validation do not claim that external resources were created.
