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
| Orchestration/state | Live-proven | Independent 09:00/10:00 ET schedules, a shared end-to-end executor, cursor state, durable stage checkpoints, terminal truth, and exact-job Cloud Monitoring failure policies for both pipelines | Schedule-miss and freshness SLOs are not yet implemented |
| Release evidence | Live-proven in retained sandbox and clean project | HubSpot authenticated recovery/replay canaries passed with stable row hash, both schedules are enabled, a controlled failure opened a real incident, and both Terraform roots report zero drift | WIF workflow upload, Storage Write, and optional Dataplex remain separate proofs |

Detailed execution identifiers and release boundaries are in [`release-audit.md`](release-audit.md).
