---
id: DANDER-20
title: Runnable Greenhouse to BigQuery v0
status: done
component: python
epic: runtime
depends_on: [DANDER-10, DANDER-11, DANDER-12, DANDER-13, DANDER-16, DANDER-18]
created: 2026-07-29
---

## Context

The graph and connector configuration models are implemented, but the runtime path is still
stubbed. The first product slice must follow the project decision to prove a low-friction source
end-to-end before adding enterprise connectors.

## Acceptance Criteria

- [x] Resolve connector secrets through GCP Secret Manager or an environment-variable reference,
      audit every access without logging the value, and apply Greenhouse API-key basic auth.
- [x] Load and validate a connector YAML, extract a configured endpoint through dlt REST API
      pagination, and pass the persisted watermark as the endpoint's cursor query parameter.
- [x] Write each batch idempotently to BigQuery with a staging-table SCD1 `MERGE`, rejecting
      invalid identifiers, missing business keys, and inconsistent record shapes.
- [x] Persist the maximum successful response cursor in a BigQuery control table only after the
      target write succeeds.
- [x] `dander run greenhouse --dry-run` produces a credential-free execution plan; a non-dry run
      executes the source → writer → watermark path.
- [x] `dander init` can safely plan the BigQuery bootstrap and requires an explicit flag before
      applying Terraform.
- [x] Unit tests cover secret resolution/auditing, auth, dlt configuration, MERGE construction,
      watermark commit ordering, CLI dry-run, and failure behavior without network or credentials.
- [x] README, `.env.example`, connector config, Decision Log, and `HANDOFF.md` accurately describe
      the delivered v0 and its limits.
- [x] Ruff, Ruff format check, strict mypy, pytest, and CLI smoke checks pass.

## Design

Keep orchestration dependent on the existing `Source`, `WritePattern`, `WatermarkStore`, and
`SecretStoreProvider` abstractions. `DltRestSource` adapts declarative `SourceConfig` to dlt's REST
source. `BigQueryScd1Writer` and `BigQueryWatermarkStore` receive injected clients for unit tests.
`PipelineRunner` owns commit ordering but not provider details. CLI composition is the only place
that creates concrete GCP clients.

The legacy `Endpoint.incremental_cursor` remains the response field. A new optional
`Endpoint.cursor_param` names the request query parameter when it differs (Greenhouse:
`updated_at` response field, `updated_after` request parameter).

## Review Log

### 2026-07-29 — PASS

Reviewed the runtime against the acceptance criteria and steering contract. External clients are
dependency-injected, unit tests perform no network or cloud mutations, secret values are never
logged, the staging table is cleaned on failures, and cursor state advances only after a successful
write. All repository quality gates pass; operational limits are documented in the README.
