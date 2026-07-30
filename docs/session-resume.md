# Session Resume — 2026-07-30

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
- Do not push, open a PR, apply Terraform, deploy an image, publish Dataplex metadata, or change
  billing/scheduling without explicit authorization.

## Git and validation state

- Repository: `/Users/harrison/Documents/dander`
- Branch: `codex/dander-v0`
- `origin` is `WagnerJ-Dev/dander`; `fork` is the user's GitHub fork.
- The fork is public and the branch has an open draft PR into upstream `main`. Confirm
  synchronization with `git status -sb` and
  `git log --oneline fork/codex/dander-v0..HEAD`.
- Last full code gate: Ruff and formatting passed, strict mypy passed across 92 source files,
  439 tests passed, and Terraform formatting/validation passed.
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

1. Decide whether to pause the enabled daily scheduler before changing the runtime image.
2. If candidate/contact integration is next, have the user create and authorize a free HubSpot
   developer test account; use invented or provider-supplied sample records only.
3. With explicit approval, build/push an immutable image, review a saved Terraform plan, keep the
   scheduler paused, and run the full ingestion → transform/test → registry path once manually.
4. Treat live Storage Write and Dataplex publication as separate, deliberately authorized tests.

Synthetic data can validate the complete Dander-controlled pipeline. A real vendor sandbox is
needed only to prove the vendor's actual authentication, undocumented response behavior, scopes,
and rate-limit enforcement.
