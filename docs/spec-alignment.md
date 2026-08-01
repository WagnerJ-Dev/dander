# Upstream Spec Alignment

This ledger maps `steering/00-project-overview.md` to current code and observed runtime state.

| Module | Status | Current evidence | Deliberate boundary |
|---|---|---|---|
| Security | Live-proven | Secret Manager references, per-pipeline accessor bindings, separate bootstrap/runtime/scheduler identities, account-scoped billing visibility, and no service-account keys | Other private vendors require their own tenant credentials |
| Hybrid ingestion | Live-proven | Config-driven dlt REST paths plus hand-rolled enterprise `Source`; hosted Greenhouse and authenticated HubSpot executions succeeded | Workday/NetSuite/Xactly remain provider-specific extensions |
| BigQuery writer | Live-proven for hosted SCD1 | Additive raw/staging relations, controlled HubSpot update/replay proof, stable watermarks, and preserved row counts | Live Storage Write/SCD2 are covered offline, not by this proof |
| Transform | Live-proven | Restricted `ref()` DAG, topological execution, materialization, and generic tests ran inside both Cloud Run jobs | None for the demonstrated staging slice |
| Metadata spine | Live-proven | Atomic per-pipeline BigQuery snapshots contain sources, models, columns, upstreams, tests, and metrics; CLI list/show/lineage/metrics/runs work live | Dataplex is an optional projection and was not mutated |
| Bootstrap CLI | Live-proven for reconciliation | `dander init` owns state bootstrap, administrative IAM, image publication, Terraform plan/apply, and safe defaults; real upgrade plan is idempotent | Fresh billable-project creation/apply awaits explicit approval |
| Orchestration/state | Live-proven | Independent jobs/schedules, a shared end-to-end executor, cursor state, durable stage checkpoints, and terminal truth for both pipelines | HubSpot remains intentionally paused |
| Release evidence | Live-proven | Two passing deployment summaries, two successful executor runs, metadata/run queries, secret-scope inspection, row counts, and a zero-drift plan | Ignored evidence must be attached explicitly if a PR/release process requires it |

Detailed execution identifiers and release boundaries are in [`release-audit.md`](release-audit.md).
