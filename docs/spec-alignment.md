# Upstream Spec Alignment

This is the completion ledger for the architecture in `steering/00-project-overview.md`. “Partial”
means the named upstream responsibility still has at least one unimplemented or unverified part.

| Upstream module | Status | Current evidence | Missing proof |
|---|---|---|---|
| Security | Partial | Secret Manager and environment stores; API-key/basic, no-auth, and OAuth2 client-credentials strategies; audited resolution tests | JWT and OAuth1 TBA strategies; runtime IAM provisioning for secret access |
| Hybrid ingestion | Partial | Config-driven dlt REST extraction, pagination/backoff, Greenhouse public and Harvest paths | A concrete `EnterpriseSource`; runtime field-cast execution and broader schema evolution |
| BigQuery Writer | Partial | Idempotent SCD1 staging/MERGE, sandbox replace, BigQuery/SQLite watermarks | SCD2, snapshot, and incremental writers; chunked/streaming loads; controlled target schema evolution |
| Transform | Partial | Typed YAML, restricted `ref()` compilation, DAG ordering, view/table builds, four generic tests | Incremental materialization; execution of the visual pipeline mapping/join/custom-code model |
| Metadata spine/catalog | Implemented locally | One YAML projects to transforms/tests, deterministic semantic JSON, and reusable Dataplex system-aspect requests | Live aspect publication intentionally unverified because metadata storage is billable |
| Bootstrap CLI | Partial | Remote Terraform state, BigQuery datasets, Artifact Registry, least-privilege scheduled Cloud Run job | One-command Secret Manager, WIF, cost guard, image build/deploy, and full runtime bootstrap |
| Orchestration/state | Substantially implemented | Cloud Scheduler invokes Cloud Run; BigQuery watermark commits only after successful writes | Transform/catalog scheduling in the hosted job; operational run history/control table |
| Compliance/release | External gate | Public-data path contains no customer credential or HR row data | Upstream-required OSS/legal approval before any private HR/customer-data release |

## Current critical path

1. Finish the metadata-spine catalog slice and keep Dataplex publication explicit.
2. Make `dander init` provision the complete runtime through reviewed Terraform.
3. Implement remaining idempotent writer modes and transform incremental materialization.
4. Prove one hand-rolled enterprise connector with fake/provider sandbox data.
5. Run a requirement-by-requirement release audit; do not treat passing unit tests as production
   readiness or as satisfying the external legal gate.
