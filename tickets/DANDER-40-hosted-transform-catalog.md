---
id: DANDER-40
title: Run transforms and catalog compilation in the hosted pipeline
status: complete
component: orchestration
epic: runtime
depends_on: [DANDER-25, DANDER-26, DANDER-27]
created: 2026-07-29
---

## Acceptance Criteria

- [x] Successful hosted ingestion builds and tests the public Greenhouse jobs model.
- [x] The semantic registry compiles only after transform assertions pass.
- [x] The container includes the model project required by the runtime command.
- [x] Runtime IAM permits writes to declared transform datasets without broad project data access.
- [x] Dataplex publication, API enablement, and catalog IAM are explicit and disabled by default.
- [x] The daily schedule remains paused until a complete manual run is verified.
- [x] Documentation, strict typing, tests, and Terraform validation pass.
