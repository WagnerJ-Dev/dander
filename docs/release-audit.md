# Dander v0 Release Audit

Audited against the live `WagnerJ-Dev/dander` north star on 2026-07-29. “Implemented locally”
means code, offline tests, and static infrastructure validation exist. It does not imply that
provider credentials, billable cloud mutations, or the upstream legal gate have been cleared.

## Requirement evidence

| Upstream requirement | Status | Evidence |
|---|---|---|
| Secret Manager backing store and audited credential access | Implemented locally | `security/secret_manager.py`; environment-to-managed-resource routing; value-free access events; secret-resolution tests |
| API/basic, OAuth2 client credentials/JWT, and OAuth1 TBA | Implemented locally | `security/`; cached/refreshable bearer tokens; Greenhouse, Marketo, Salesforce, Workday, and NetSuite templates/tests |
| Config-driven standard REST ingestion on dlt | Implemented locally | `ingestion/dlt_backed.py`; five pagination strategies; public Greenhouse and Marketo templates |
| Hand-rolled enterprise ingestion behind `Source` | Implemented locally | `WorkdayRaasSource`; injected transport; paging, cursor, envelope, casting, and retry tests |
| Per-source rate limiting and bounded backoff | Implemented locally | dlt token-bucket session plus safe-read retries; Workday bounded retry path; metadata-only retry events |
| Inferred types plus per-field BigQuery overrides | Implemented locally | dlt inference on standard REST; declared scalar casts for enterprise sources; additive declared target schemas |
| SCD1, SCD2, snapshots, and incremental writes | Implemented locally | `writer/bigquery.py`; unique staging, deduplication, transactional history, cursor validation, and rerun tests |
| Storage Write API versus load jobs by workload | Implemented locally | explicit transport config; bounded load jobs; offset-checked pending streams committed atomically before keyed merge |
| `ref()` DAG and topological transform execution | Implemented locally | restricted Jinja compilation, sqlglot validation, cycle/unknown-ref rejection, and ordered BigQuery builds |
| Materializations and four generic test types | Implemented locally | view/table/incremental SQL; not-null, unique, accepted-values, and relationship assertions |
| One model YAML feeds transform, catalog, and semantics | Implemented locally | typed sidecars compile executable tests, deterministic semantic JSON, and non-deleting Dataplex aspect requests |
| Terraform bootstrap for datasets, secrets, IAM/WIF, and Cloud Run | Implemented locally | modular HCL and `dander init`; immutable images; repository/ref-scoped GitHub OIDC; secret values excluded from state |
| Scheduled execution and restart state | Implemented locally | paused-first Scheduler → Cloud Run job; guarded ingestion → selected transforms/tests → registry; BigQuery/SQLite cursors and run summaries |

Transform materializations use the same idempotent BigQuery contracts as the record writers, but
query-based transforms compile SQL directly instead of passing materialized rows through the
Python `WritePattern` interface. This avoids pulling transform data out of BigQuery.

## Release boundaries

- The credential-free Greenhouse path is the only live source proof available without a customer
  account. Marketo and enterprise provider exchanges are tested offline and require tenant access.
- Storage Write, hosted Cloud Run, the live billing kill switch, and Dataplex publication still
  require explicit billable-project authorization. Free allowances are not a hard cost ceiling.
- Endpoint extraction is still accumulated in memory before a logical write. Bounded writer
  requests protect BigQuery payload size, not total-process memory for very large sources.
- Nested/repeated automatic schema evolution is intentionally unsupported; only declared nullable
  scalar additions are automatic.
- A public or customer-data release remains blocked by the upstream requirement for internal
  OSS/legal review. Engineering checks cannot satisfy that approval.

## Verdict

This branch is a reasonable, runnable v0 of the stated architecture and has local implementation
evidence for every named module. It is not yet a production-certified or legally cleared release.
The remaining blockers need external authority, credentials, or a willingness to incur cloud cost;
they are not gaps that should be papered over with mocks.
