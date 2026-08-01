# Session Resume — 2026-08-01

Read `HANDOFF.md`, `docs/decisions.md`, `docs/spec-alignment.md`, and `docs/release-audit.md` before changing code or cloud resources.

## Git state

- Repository: `/Users/harrison/Documents/dander`.
- Working branch: `codex/multi-pipeline-control-plane`; base `main`/`origin/main` is `15b7543`.
- Implementation history includes `605318e`, `7a1698c`, `a7da7df`, and `57f6a8a`; the clean-project compatibility fixes and proof record are the current branch tip.
- The branch is local and unpublished. Do not push or open a PR without user authorization.
- The branch includes the additive control plane, shared executor/metadata spine, clean-project bootstrap fixes, verifier guidance, and refreshed release evidence.

## Clean-project proof

- Approved project: `dander-proof-harrison-20260801`; region `us-central1`; remote state bucket `dander-proof-harrison-20260801-dander-state`.
- `dander init --apply` completed with immutable image `sha256:d81d865a…4c125`, four datasets, two jobs, two `PAUSED` schedulers, an empty HubSpot secret container, and a USD 5 simulation-only cost guard.
- Greenhouse executions `dander-greenhouse-public-8x9j9`, `-9ndj6`, and `-g77d2` all succeeded. Each extracted/affected 21 rows, built one model, passed three tests, and published one metadata asset; replay counts and hashes matched.
- Metadata list/metrics/lineage/runs, both deployment verifiers, retained inventory, and the follow-up `No changes` plan passed. Sanitized evidence is ignored under `evidence/clean-project-20260801`.
- The project is intentionally retained. Do not enable schedules, add the HubSpot token, publish Dataplex, delete resources, or make the cost guard live without new approval.

## Retained sandbox state

- Project: `dander-sbx-harrison-20260729`; region: `us-central1`; remote state: `gs://dander-sbx-harrison-20260729-tfstate/dander/state`.
- Both jobs use immutable manifest digest `sha256:a4ec1a3eca1e4c3963ea461c9134ddc1d4d00b134fd30c2f13c4c57805962289`.
- Greenhouse job/scheduler: `dander-greenhouse-public` / `dander-greenhouse-public-daily`, scheduler `ENABLED`.
- HubSpot job/scheduler: `dander-hubspot-companies` / `dander-hubspot-companies-daily`, scheduler `PAUSED`.
- Only `dander-runtime-hubspot` can access `hubspot-private-app-token`.
- `raw`, `staging`, `marts`, and `dander_meta` exist; a fresh Terraform plan reports no changes.

## Retained sandbox proof

- Greenhouse execution `dander-greenhouse-public-nm8wg` and Dander run `2441c4843aab418fb9d6e9523eb9b0c2` succeeded with 21 extracted/affected rows, one model, three tests, and one asset.
- HubSpot execution `dander-hubspot-companies-l2g6c` and Dander run `6e3258bc0eab4a47ad1bfeae38704912` succeeded with one model, three tests, and one asset after controlled proof data had been removed.
- BigQuery retains 25 Greenhouse and 4 HubSpot rows in both raw and staging.
- `dander_meta._dander_catalog` has schema-v2 snapshots for both pipelines and `dander_meta._dander_runs` has their terminal outcomes.
- Read-only deployment verification passes for both pipelines; sanitized output is ignored under `evidence/platform-*`.
- The inventory collector passes read-only against the sandbox: one state bucket, four datasets, two jobs, two schedules, six Dander service accounts, one secret, and one image repository.

## Safety boundaries

- Do not enable HubSpot scheduling, publish Dataplex aspects, create a new billable proof project, or change the cost guard without explicit user approval.
- Secret values must remain in Secret Manager and out of Git, logs, plans, and chat.
- Clean-project proof authorization is consumed. Any later cloud mutation—including teardown—requires its own scope and approval.
