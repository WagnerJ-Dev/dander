# Upstream Spec Alignment

This is the completion ledger for the architecture in `steering/00-project-overview.md`. “Partial”
means the named upstream responsibility still has at least one unimplemented or unverified part.

| Upstream module | Status | Current evidence | Missing proof |
|---|---|---|---|
| Security | Implemented locally | Audited Secret Manager/environment stores; API-key/basic, no-auth, OAuth2 client-credentials, OAuth2 JWT bearer, and OAuth1 TBA strategies; per-secret runtime IAM and keyless GitHub WIF | Live provider exchanges intentionally require customer credentials |
| Hybrid ingestion | Substantially implemented | Config-driven dlt REST extraction plus concrete Workday RaaS enterprise execution with auth, pagination, bounded backoff, cursor params, and BigQuery scalar casts | Live tenant proof intentionally unavailable without customer access; broader nested schema evolution |
| BigQuery Writer | Substantially implemented | Idempotent SCD1 and cursor-validated incremental MERGE, append-only partitioned snapshots, transactional SCD2 history, sandbox replace, committed watermarks, and target-node writer dispatch | Bounded chunk/streaming loads; controlled target schema evolution |
| Transform | Implemented locally | Typed YAML, restricted `ref()` compilation, DAG ordering, view/table/incremental builds, four generic tests, and safe visual mapping/expression/custom-transform/two-input join SQL compilation | Live BigQuery execution remains covered by injected clients rather than a billable integration run |
| Metadata spine/catalog | Implemented locally | One YAML projects to transforms/tests, deterministic semantic JSON, and reusable Dataplex system-aspect requests | Live aspect publication intentionally unverified because metadata storage is billable |
| Bootstrap CLI | Substantially implemented | One reviewed `dander init` plan covers BigQuery, Secret Manager, keyless GitHub WIF, Artifact Registry, scheduled Cloud Run, and a simulation-first project cost guard | Pre-build/push of the immutable runtime image remains a prerequisite; live cost-guard apply intentionally unverified because it deploys billable services |
| Orchestration/state | Substantially implemented | Cloud Scheduler invokes Cloud Run; BigQuery watermark commits only after successful writes; SQLite/BigQuery run history records terminal aggregates | Transform/catalog scheduling in the hosted job |
| Compliance/release | External gate | Public-data path contains no customer credential or HR row data | Upstream-required OSS/legal approval before any private HR/customer-data release |

## Current critical path

1. Add bounded writer loads and controlled nested schema evolution.
2. Add hosted transform/catalog execution.
3. Run a requirement-by-requirement release audit; do not treat passing unit tests as production
   readiness or as satisfying the external legal gate.
