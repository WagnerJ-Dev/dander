# Session Resume — 2026-07-31

Read `HANDOFF.md`, `docs/decisions.md`, `docs/spec-alignment.md`, and `docs/release-audit.md` before changing code or cloud resources.

## Git state

- Repository: `/Users/harrison/Documents/dander`.
- Working branch: `codex/multi-pipeline-control-plane`; base `main`/`origin/main` is `15b7543`.
- Implementation commits: `605318e` (project-defined hosted pipelines) and `7a1698c` (end-to-end execution/control plane).
- The branch is local and unpublished. Do not push or open a PR without user authorization.
- The branch also includes the final Terraform dataset-ordering fix, verifier guidance, and refreshed release evidence.

## Retained sandbox state

- Project: `dander-sbx-harrison-20260729`; region: `us-central1`; remote state: `gs://dander-sbx-harrison-20260729-tfstate/dander/state`.
- Both jobs use immutable manifest digest `sha256:a4ec1a3eca1e4c3963ea461c9134ddc1d4d00b134fd30c2f13c4c57805962289`.
- Greenhouse job/scheduler: `dander-greenhouse-public` / `dander-greenhouse-public-daily`, scheduler `ENABLED`.
- HubSpot job/scheduler: `dander-hubspot-companies` / `dander-hubspot-companies-daily`, scheduler `PAUSED`.
- Only `dander-runtime-hubspot` can access `hubspot-private-app-token`.
- `raw`, `staging`, `marts`, and `dander_meta` exist; a fresh Terraform plan reports no changes.

## Latest proof

- Greenhouse execution `dander-greenhouse-public-nm8wg` and Dander run `2441c4843aab418fb9d6e9523eb9b0c2` succeeded with 21 extracted/affected rows, one model, three tests, and one asset.
- HubSpot execution `dander-hubspot-companies-l2g6c` and Dander run `6e3258bc0eab4a47ad1bfeae38704912` succeeded with one model, three tests, and one asset after controlled proof data had been removed.
- BigQuery retains 25 Greenhouse and 4 HubSpot rows in both raw and staging.
- `dander_meta._dander_catalog` has schema-v2 snapshots for both pipelines and `dander_meta._dander_runs` has their terminal outcomes.
- Read-only deployment verification passes for both pipelines; sanitized output is ignored under `evidence/platform-*`.

## Safety boundaries

- Do not enable HubSpot scheduling, publish Dataplex aspects, create a new billable proof project, or change the cost guard without explicit user approval.
- Secret values must remain in Secret Manager and out of Git, logs, plans, and chat.
- A separate clean-project apply is the only core release proof still requiring external authorization; the existing-project `dander init` upgrade path already produces a no-change plan.
