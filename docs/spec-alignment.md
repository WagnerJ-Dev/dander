# Upstream Spec Alignment

This is the completion ledger for the architecture in `steering/00-project-overview.md`. “Partial”
means the named upstream responsibility still has at least one unimplemented or unverified part.

| Upstream module | Status | Current evidence | Missing proof |
|---|---|---|---|
| Security | Implemented locally | Audited Secret Manager/environment stores; API-key/basic, no-auth, OAuth2 client-credentials, OAuth2 JWT bearer, and OAuth1 TBA strategies; per-secret runtime IAM and keyless GitHub WIF | Live provider exchanges intentionally require customer credentials |
| Hybrid ingestion | Implemented locally | Config-driven dlt REST extraction with per-source pacing/retry, Greenhouse and Marketo templates, plus concrete Workday RaaS enterprise execution with auth, pagination, cursor params, and BigQuery scalar casts | Live tenant proof intentionally unavailable without customer access; broader nested schema evolution |
| BigQuery Writer | Implemented locally | Idempotent SCD1/incremental MERGE, append-only snapshots, transactional SCD2, sandbox replace, bounded load jobs, additive scalar evolution, and selectable atomic pending-stream Storage Write staging | Live Storage Write integration intentionally unverified because it requires a billing-linked project |
| Transform | Implemented locally | Typed YAML, restricted `ref()` compilation, DAG ordering, view/table/incremental builds, four generic tests, and safe visual mapping/expression/custom-transform/two-input join SQL compilation | Live BigQuery execution remains covered by injected clients rather than a billable integration run |
| Metadata spine/catalog | Implemented locally | One YAML projects to transforms/tests, deterministic semantic JSON, and reusable Dataplex system-aspect requests | Live aspect publication intentionally unverified because metadata storage is billable |
| Bootstrap CLI | Implemented locally | One reviewed `dander init` plan covers BigQuery, Secret Manager, keyless GitHub WIF, Artifact Registry, the scheduled public pipeline, opt-in Dataplex IAM, and a simulation-first project cost guard | Pre-build/push of the immutable runtime image remains a prerequisite; live cost-guard apply intentionally unverified because it deploys billable services |
| Orchestration/state | Implemented locally | Cloud Scheduler invokes a guarded public ingestion, selected transform/test build, and registry compilation; BigQuery watermarks commit only after successful writes; SQLite/BigQuery run history records terminal aggregates | Live hosted execution intentionally unverified because it requires a billing-linked project |
| Compliance/release | External gate | Public-data path contains no customer credential or HR row data | Upstream-required OSS/legal approval before any private HR/customer-data release |

The requirement-by-requirement verdict and explicit release boundaries are in
[`release-audit.md`](release-audit.md).
