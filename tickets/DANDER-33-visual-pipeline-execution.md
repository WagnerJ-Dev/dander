---
id: DANDER-33
title: Compile visual mappings and dispatch target writers
status: complete
component: pipeline
epic: runtime
depends_on: [DANDER-8, DANDER-15, DANDER-16, DANDER-30]
created: 2026-07-29
---

## Acceptance Criteria

- [x] A validated linear source-to-transform-to-target graph compiles into deterministic BigQuery
      SQL with explicit columns.
- [x] Direct mappings, constants, scalar expressions, target casts, and trusted custom transforms
      execute without Python `eval` or arbitrary code loading.
- [x] Expressions are parsed as row-local SQL and enforce exact declared inputs plus a function
      allow-list.
- [x] Target writer configuration resolves to every concrete BigQuery write pattern.
- [x] Fan-in, incomplete mappings, unsafe relations, and the ambiguous current join encoding fail
      closed with structural error messages.
- [x] Documentation, strict typing, tests, and full checks pass.

## Review Log

The compiler supports the unambiguous linear graph subset. Joins remain declarative until the graph
schema gains a distinct join-output node; interpreting the current right endpoint as both an input
and output would create hidden execution semantics.
