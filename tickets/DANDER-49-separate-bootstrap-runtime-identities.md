---
id: DANDER-49
title: Separate bootstrap and runtime identities
status: complete
component: terraform
epic: bootstrap
created: 2026-07-30
---

## Acceptance criteria

- [x] Terraform creates a dedicated `dander-bootstrap` identity with provisioning roles.
- [x] Cloud Run and Scheduler retain dedicated workload identities.
- [x] GitHub WIF can impersonate only the deployment identity and named workload accounts, never the
      bootstrap identity.
