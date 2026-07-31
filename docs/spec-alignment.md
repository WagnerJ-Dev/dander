# Upstream Spec Alignment

This is the completion ledger for the architecture in `steering/00-project-overview.md`. “Partial”
means the named upstream responsibility still has at least one unimplemented or unverified part.

| Upstream module | Status | Current evidence | Missing proof |
|---|---|---|---|
| Security | Implemented locally | Audited Secret Manager/environment stores; API-key/basic, no-auth, OAuth2 client-credentials, OAuth2 JWT bearer, and OAuth1 TBA strategies; per-secret runtime IAM and keyless GitHub WIF | Live provider exchanges intentionally require customer credentials |
| Hybrid ingestion | Implemented locally | Config-driven dlt REST extraction with per-source pacing/retry, live public Greenhouse/Lever/Ashby connectors, a Marketo template, plus concrete Workday RaaS enterprise execution with auth, pagination, cursor params, and BigQuery scalar casts | Live private-tenant proof intentionally unavailable without customer access; broader nested schema evolution |
| BigQuery Writer | Implemented locally | Idempotent SCD1/incremental MERGE, append-only snapshots, transactional SCD2, sandbox replace, bounded load jobs, additive scalar evolution, and selectable atomic pending-stream Storage Write staging | A billing-linked project is available, but the real Storage Write service path has not yet been run |
| Transform | Implemented locally | Typed YAML, restricted `ref()` compilation, DAG ordering, view/table/incremental builds, four generic tests, safe visual SQL compilation, and a live selected Greenhouse view/test proof | Incremental and visual transform execution remain proven offline rather than through additional billable runs |
| Metadata spine/catalog | Implemented locally | One YAML projects to transforms/tests, deterministic semantic JSON, reusable Dataplex system-aspect requests, and a live read-only entry lookup | Dataplex aspect mutation remains intentionally unrun because stored metadata may be billable |
| Bootstrap CLI | Implemented locally | Stage-zero `infra/bootstrap-admin` creates the state bucket, Artifact Registry repository, and bootstrap identity; `dander init` requires impersonation; `dander verify deployment` writes sanitized evidence | A real stage-zero/platform apply and retained evidence bundle are still required |
| Orchestration/state | Implemented locally | Cloud Scheduler invokes guarded public ingestion; BigQuery watermarks commit only after successful writes; SQLite/BigQuery run history records terminal aggregates; manual workflow can run hosted transform proofs | A real clean-project run and retained workflow evidence are still required |
| Evidence/release gates | Implemented locally | Enforced CI, closed evidence schemas, resource-scoped IAM/cost checks, and a protected manual live-proof workflow | No live proof is claimed until a workflow artifact is reviewed |
| Compliance/release | Context-dependent | Public-data path contains no customer credential or HR row data; sensitive-system names are hypothetical connector scope, not company provenance | Normal provenance, licensing, and privacy review if employer-owned material or non-public data is ever introduced |

The requirement-by-requirement verdict and explicit release boundaries are in
[`release-audit.md`](release-audit.md).
