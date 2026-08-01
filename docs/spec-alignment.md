# Upstream Spec Alignment

This ledger maps `steering/00-project-overview.md` to current code and observed runtime state.

| Module | Status | Current evidence | Deliberate boundary |
|---|---|---|---|
| Security | Live-proven | Secret Manager references, per-pipeline accessor bindings, separate bootstrap/runtime/scheduler identities, account-scoped billing visibility, and no service-account keys | Other private vendors require their own tenant credentials |
| Hybrid ingestion | Live-proven | Config-driven dlt REST paths plus hand-rolled enterprise `Source`; hosted Greenhouse and authenticated HubSpot executions succeeded | Workday/NetSuite/Xactly remain provider-specific extensions |
| BigQuery writer | Live-proven for hosted SCD1 | Additive raw/staging relations, controlled HubSpot update/replay proof, stable watermarks, and preserved row counts | Live Storage Write/SCD2 are covered offline, not by this proof |
| Transform | Live-proven | Restricted `ref()` DAG, topological execution, materialization, and generic tests ran inside both Cloud Run jobs | None for the demonstrated staging slice |
| Metadata spine | Live-proven | Atomic per-pipeline BigQuery snapshots contain sources, models, columns, upstreams, tests, and metrics; CLI list/show/lineage/metrics/runs work live | Dataplex is an optional projection and was not mutated |
| Bootstrap CLI | Live-proven from clean project and reconciliation | `dander init --apply` created stage zero, published the image, and applied the full platform in `dander-proof-harrison-20260801`; the immediate follow-up plan returned `No changes` | Project creation and billing linkage remain administrator prerequisites |
| Orchestration/state | Live-proven | Independent jobs/schedules, a shared end-to-end executor, cursor state, durable stage checkpoints, and terminal truth for both pipelines | HubSpot remains intentionally paused |
| Release evidence | Live-proven in retained sandbox and clean project | Clean-project bootstrap/final verifiers passed for both paused jobs; three Greenhouse runs, replay hashes, metadata queries, zero drift, and retained-resource inventory passed | WIF workflow upload, authenticated HubSpot, Storage Write, and optional Dataplex remain separate proofs |

Detailed execution identifiers and release boundaries are in [`release-audit.md`](release-audit.md).
