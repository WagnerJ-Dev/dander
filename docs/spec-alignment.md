# Upstream Spec Alignment

This is the completion ledger for the architecture in `steering/00-project-overview.md`. “Partial”
means the named upstream responsibility still has at least one unimplemented or unverified part.

| Upstream module | Status | Current evidence | Missing proof |
|---|---|---|---|
| Security | Partial | Secret Manager and environment stores; API-key/basic, no-auth, and OAuth2 client-credentials strategies; per-secret runtime IAM and keyless GitHub WIF | JWT and OAuth1 TBA strategies |
| Hybrid ingestion | Substantially implemented | Config-driven dlt REST extraction plus concrete Workday RaaS enterprise execution with auth, pagination, bounded backoff, cursor params, and BigQuery scalar casts | Live tenant proof intentionally unavailable without customer access; broader nested schema evolution |
| BigQuery Writer | Substantially implemented | Idempotent SCD1 and cursor-validated incremental MERGE, append-only partitioned snapshots, transactional SCD2 history, sandbox replace, committed watermarks, and target-node writer dispatch | Bounded chunk/streaming loads; controlled target schema evolution |
| Transform | Substantially implemented | Typed YAML, restricted `ref()` compilation, DAG ordering, view/table/incremental builds, four generic tests, and safe linear visual mapping/expression/custom-transform SQL compilation | Executable joins require a distinct join-output relation in the graph schema |
| Metadata spine/catalog | Implemented locally | One YAML projects to transforms/tests, deterministic semantic JSON, and reusable Dataplex system-aspect requests | Live aspect publication intentionally unverified because metadata storage is billable |
| Bootstrap CLI | Substantially implemented | One reviewed `dander init` plan covers BigQuery, Secret Manager, keyless GitHub WIF, Artifact Registry, scheduled Cloud Run, and a simulation-first project cost guard | Pre-build/push of the immutable runtime image remains a prerequisite; live cost-guard apply intentionally unverified because it deploys billable services |
| Orchestration/state | Substantially implemented | Cloud Scheduler invokes Cloud Run; BigQuery watermark commits only after successful writes | Transform/catalog scheduling in the hosted job; operational run history/control table |
| Compliance/release | External gate | Public-data path contains no customer credential or HR row data | Upstream-required OSS/legal approval before any private HR/customer-data release |

## Current critical path

1. Revise the join graph shape to give joins two inputs and one distinct output, then compile it.
2. Add bounded writer loads and controlled nested schema evolution.
3. Add hosted transform/catalog execution and run-history observability.
4. Add the remaining JWT and OAuth1 TBA authentication strategies.
5. Run a requirement-by-requirement release audit; do not treat passing unit tests as production
   readiness or as satisfying the external legal gate.
