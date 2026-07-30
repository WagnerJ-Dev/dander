---
id: DANDER-35
title: Execute visual two-input joins
status: complete
component: pipeline
epic: runtime
depends_on: [DANDER-33]
created: 2026-07-29
---

## Acceptance Criteria

- [x] A transform node can name exactly two incoming nodes, a join type, and ordered equality keys.
- [x] The transform node is the distinct join output and its incoming edges map explicit columns.
- [x] Both inputs compile recursively, so sources or upstream transforms can feed the join.
- [x] Missing inputs, undeclared keys, duplicate output mappings, and legacy edge joins fail closed.
- [x] Existing graph files and declarative edge joins remain loadable without behavior changes.
- [x] Documentation, strict typing, tests, and full checks pass.

## Review Log

The executable shape is additive under `TransformNodeConfig.join`. It does not reinterpret or
remove the legacy edge-level declaration, avoiding a silent migration of existing authored graphs.
