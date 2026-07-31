---
id: DANDER-50
title: Add deployment verification command
status: complete
component: cli
epic: bootstrap
created: 2026-07-30
---

## Acceptance criteria

- [x] `dander verify deployment` checks project, datasets, remote state, and optional runtime,
      Scheduler, IAM, Secret Manager, and cost-guard resources with read-only calls.
- [x] Checks are retained as explicit pass/fail results and a failed check exits non-zero.
- [x] JSON output is sanitized and suitable for CI evidence retention.
