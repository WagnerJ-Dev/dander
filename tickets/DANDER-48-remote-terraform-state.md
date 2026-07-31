---
id: DANDER-48
title: Configure and verify remote Terraform state
status: complete
component: terraform
epic: bootstrap
created: 2026-07-30
---

## Acceptance criteria

- [x] `dander init` initializes the GCS backend from literal backend arguments.
- [x] The deployment verifier confirms initialized GCS backend metadata and a read-only state pull.
- [x] State payloads are not copied into evidence artifacts.
