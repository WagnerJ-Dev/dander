---
id: DANDER-51
title: Prove clean-project bootstrap
status: completed
component: operations
epic: bootstrap
created: 2026-07-30
---

## Acceptance criteria

- [x] Run `dander init plan` from a clean billing-linked proof project with an approved bootstrap
      identity.
- [x] Apply the reviewed plan with runtime and Scheduler paused.
- [x] Attach `evidence/bootstrap-summary.json` from `dander verify deployment` to the proof run.
- [x] Record teardown or an explicit retained-resource inventory before merge.

Completed interactively on 2026-08-01 in approved project
`dander-proof-harrison-20260801`. `dander init --apply` created stage zero, published immutable
image `sha256:d81d865a…4c125`, and deployed both additive jobs with both schedulers `PAUSED`, the
HubSpot secret container empty, and the USD 5 cost guard in simulation mode.

Greenhouse execution `dander-greenhouse-public-8x9j9` succeeded with 21 extracted/affected rows,
one model, three tests, and one catalog asset. Two subsequent replay executions retained 21 rows
and identical stable hashes. Metadata list/metrics/lineage/runs queries succeeded, both final
deployment verifiers passed, and a fresh `dander init` plan reported `No changes`.

Sanitized evidence is retained locally under ignored `evidence/clean-project-20260801`; inventory
records one state bucket, four datasets, two jobs, two schedulers, seven service accounts, one
secret container, and one repository. The project and resources were retained; nothing was
deleted, no schedule was enabled, and Dataplex was not published.
