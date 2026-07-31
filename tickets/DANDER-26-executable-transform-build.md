---
id: DANDER-26
title: Executable BigQuery transform build
status: done
component: transform
epic: transform
depends_on: [DANDER-1, DANDER-20]
created: 2026-07-29
---

## Context

Dander can ingest and schedule public Greenhouse jobs into BigQuery, but the original product
promise continues through owned SQL transforms, generic tests, and a shared YAML metadata spine.
The current transform package only extracts `ref()` calls and cannot build a model.

## Acceptance Criteria

- [x] SQL models and YAML sidecars load through typed, fail-closed boundary validation.
- [x] Model references resolve to raw relations or model outputs and sort topologically; unknown
      references and cycles fail before any BigQuery query runs.
- [x] Jinja compilation produces validated BigQuery SQL and materializes views or tables.
- [x] Not-null, unique, accepted-values, and relationship tests execute as assertion queries.
- [x] `dander build` materializes selected models and tests them; `dander test` tests existing
      selected relations without rebuilding.
- [x] A public Greenhouse jobs model builds in `staging` and its declared tests pass live.
- [x] Documentation, handoff, linting, formatting, strict typing, and the full test suite pass.

## Review Log

PASS — configuration and graph failures occur before warehouse mutation; compiled models must be
single read-only BigQuery queries; all four generic test kinds have unit coverage; the guarded live
view contains 21 rows with 21 unique, non-null job ids; all repository checks pass.
