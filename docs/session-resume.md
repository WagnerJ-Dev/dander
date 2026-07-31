# Session Resume — 2026-07-31

Use this file to resume Dander work in a new Codex session without reconstructing the prior
conversation. Read `HANDOFF.md`, `docs/decisions.md`, `docs/spec-alignment.md`, and
`docs/release-audit.md` before changing code or cloud resources.

## Working assumptions

- Dander is a generic EL(T) product. Workday, Salesforce, NetSuite, Xactly, and similar names are
  hypothetical connector categories; do not infer an existing-company relationship, employer
  ownership, customer records, or HR records.
- No vendor tenant credential is currently available. Never paste one into chat or commit it.
  Production references belong in Secret Manager; local values belong only in ignored environment
  files.
- The user accepts a USD 5 monthly GCP budget, but every new billable test still requires explicit
  scope. Budget reporting and billing detachment are delayed and are not a mathematical hard cap.
- Do not apply Terraform, deploy an image, publish Dataplex metadata, or change billing/scheduling
  without explicit authorization. Repository documentation may be updated through the protected
  pull-request path; repository-admin and cloud changes still require explicit scope.

## Git and validation state

- Repository: `/Users/harrison/Documents/dander`
- Admin-owned GitHub repository: `harrisonoconnorhover/dander`; upstream contribution record:
  `WagnerJ-Dev/dander` PR #1.
- Fork PR #1 was merged into `main` at
  `6eda307b69d8eac8d731eea89fa993a5096e0a9d` on 2026-07-31.
- Active ruleset `Protect main` (ID `20133128`) targets `~DEFAULT_BRANCH`. It requires pull requests,
  resolved conversations, strict/up-to-date status checks, and these checks from GitHub Actions app
  ID `15368`: Python quality, Terraform quality, Secret scan, and Container build and scan. It permits
  merge commits only and blocks force pushes and deletion.
- The repository administrator has the intentionally approved always-bypass path for emergency
  recovery. Routine work must not use it.
- Last full code gate: Ruff and formatting passed, strict mypy passed across 92 source files,
  463 tests passed, and Terraform formatting/validation passed.
- A wheel installed into a clean virtual environment, and the local amd64 Docker image contained
  the CLI, connectors, and models.
- The current/history secret-pattern scan found only the intentional detector fixture in
  `tests/pipeline/test_request_spec.py`.

## Observed GCP sandbox state

Read-only inspection on 2026-07-30 found:

- Billing enabled on the dedicated Dander sandbox project.
- A monthly USD 5 budget scoped to that project, with 80% and 100% current-spend thresholds.
- Budget notifications connected to Pub/Sub and a live Cloud Run billing-detachment service
  (`SIMULATE_DEACTIVATION=false`).
- The daily public Greenhouse Scheduler job enabled for 09:00 America/New_York.
- Two successful Cloud Run Job executions on 2026-07-29.
- The deployed immutable image uses its Docker default command (guarded public Greenhouse
  ingestion only). It does **not** contain the newer hosted transform/test/catalog command.
- The latest source branch and Docker artifact have not been deployed.

Recover the active identifiers without documenting personal account details:

```bash
gcloud config get-value project
gcloud billing projects describe "$(gcloud config get-value project)"
gcloud billing budgets list --billing-account=BILLING_ACCOUNT_ID
gcloud scheduler jobs describe dander-greenhouse-public-daily --location=us-central1
gcloud run jobs executions list --job=dander-greenhouse-public --region=us-central1
```

## What is proven

- Public Greenhouse extraction and guarded BigQuery SCD1 ingestion ran live.
- The selected Greenhouse staging view and its tests ran live with 21 unique, non-null job ids.
- Local/offline coverage proves all named auth strategies, dlt and Workday ingestion, all writer
  modes, Storage Write request semantics, transform DAG/materializations/tests, the metadata spine,
  visual graph execution, Terraform bootstrap, run history, and cost-guard behavior.
- Dataplex aspect mutation, the real Storage Write service, Marketo, and enterprise vendor token
  exchanges have not run live.
- The loopback synthetic vendor now proves the real dlt HTTP boundary across cursor and Link-header
  pagination, duplicate keys, incremental updates, and deterministic 429/500 recovery.
- Checked-in Lever and Ashby connectors completed live credential-free extraction on 2026-07-30:
  104/104 and 58/58 rows/unique ids respectively. Counts are observations, not test fixtures.

## Recommended next vertical slice

1. Restore the billing-detachment function to simulation mode and independently verify the setting.
2. Decide whether to pause the enabled daily scheduler before changing the runtime image.
3. Re-anchor the GCP WIF repository condition and protected `live-proof` environment variables to
   `harrisonoconnorhover/dander`.
4. With explicit approval, build/push an immutable image, review a saved Terraform plan, keep the
   scheduler paused, and run the full ingestion → transform/test → registry path once manually.
5. Treat HubSpot, live Storage Write, and Dataplex publication as separate deliberately authorized
   proofs. Use only synthetic HubSpot company records.

Synthetic data can validate the complete Dander-controlled pipeline. A real vendor sandbox is
needed only to prove the vendor's actual authentication, undocumented response behavior, scopes,
and rate-limit enforcement.
