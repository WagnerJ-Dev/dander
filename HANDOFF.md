# Morning Handoff

## Finished

- Added a typed `dander.yaml` control plane that keeps Greenhouse and HubSpot as independent hosted pipelines with separate jobs, schedules, identities, models, and secret scope.
- Added one end-to-end executor for ingestion, transforms/tests, durable run history, and atomic metadata snapshots with governed metrics and CLI inspection.
- Made `dander init --apply` own state-bucket bootstrap, administrative IAM, Artifact Registry image publication, datasets, Secret Manager, Cloud Run, Scheduler, and the simulation-first cost guard.
- Reconciled the sandbox to immutable image `sha256:a4ec1a3e…62289`; both pipelines completed successfully and Terraform now reports no changes.
- Captured sanitized, ignored deployment evidence for both jobs under `evidence/platform-greenhouse` and `evidence/platform-hubspot`.

## Try It

- Run `uv run dander validate`, then inspect `uv run dander metadata list --project dander-sbx-harrison-20260729` and `uv run dander metadata runs --project dander-sbx-harrison-20260729`.
- Recheck the existing environment with the explicit plan-only `dander init` command in `README.md`; it currently produces `No changes.`

## Checks

- Current full gate passes: 489 tests, Ruff, formatting, strict mypy, and both Terraform roots.
- Greenhouse execution `dander-greenhouse-public-nm8wg` succeeded: 21 extracted/affected rows, one model, three tests, and one metadata asset.
- HubSpot execution `dander-hubspot-companies-l2g6c` succeeded: source access, one model, three tests, and one metadata asset; the earlier controlled three-run update/replay proof also passed and its synthetic companies were deleted.
- BigQuery retains 25 Greenhouse and 4 HubSpot rows in both raw and staging; the durable ledger/catalog contain current snapshots for both pipelines.
- Both read-only deployment verifiers pass and a fresh Terraform detailed-exitcode plan returned 0 with no drift.

## Decisions

- Keep Greenhouse enabled and HubSpot paused until the user chooses an unattended HubSpot cadence.
- Treat `dander_meta` as the durable built-in catalog/semantic registry; Dataplex remains an optional projection.
- Keep clean-project creation as a separately approved external proof because it creates billable GCP resources.

## Remaining

- Run the single-command bootstrap once in a newly approved billing-linked proof project and retain its resource inventory or teardown record.
- Optionally publish and read back Dataplex aspects if that billable integration is required for the release claim.
- Push this branch and open a PR only when the user authorizes publication.

## Review First

- `src/dander/executor.py`
- `src/dander/cli/main.py`
- `src/dander/catalog/store.py`
