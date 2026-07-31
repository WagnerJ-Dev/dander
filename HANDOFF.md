# Morning Handoff

## Finished

- Kept Greenhouse as the primary live public demo and retained Lever/Ashby public connectors.
- Added a separate Terraform `dander-bootstrap` identity; Cloud Run, Scheduler, and GitHub WIF
  remain scoped to their workload/deployer identities.
- Added `dander verify deployment` with read-only project, BigQuery, GCS state, runtime, Scheduler,
  IAM, Secret Manager, and optional budget checks.
- Added sanitized JSON bootstrap evidence that records failed checks and exits non-zero.
- Created the owned HubSpot developer test account `Dander Integration Sandbox` (portal `246915065`).

## Try It

Run `uv run dander verify deployment --project PROJECT --json evidence/bootstrap-summary.json`
after Terraform backend initialization. Add `--runtime-job`, `--scheduler-job`, and `--secret-id`
to check the optional hosted slice. Public connector dry-runs remain available with
`uv run dander run lever_job_board --dry-run --project local-demo`.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed across 95 source files.
- `uv run pytest` — 443 passed.
- Terraform recursive formatting and root validation — passed.
- Live Lever extraction — 104 rows/104 unique ids; live Ashby — 58/58.
- Both connector CLI dry-run plans — passed with SCD1 targets.

## Decisions

- Public ATS records prove real provider shapes; synthetic records prove controlled failures.
- Bootstrap and runtime identities are separate; broad provisioning access is not attached to jobs.
- Evidence artifacts retain check statuses only, never state payloads, credentials, or records.

## Remaining

- Run DANDER-51 in a separately approved billing-linked proof project; no external apply was run here.
- Create only the minimum HubSpot private-app secret/app material when the authenticated proof is
  explicitly authorized.
- Run Marketo and enterprise tenant integrations when credentials are available.
- Run hosted, Dataplex, and Storage Write proofs only with explicit per-run cost approval.
- Stream/spool very large endpoint extracts and review nested/repeated schema evolution.

## Review First

- `src/dander/bootstrap/verify.py`
- `infra/modules/bootstrap-identity/main.tf`
- `tickets/DANDER-51-clean-project-bootstrap-proof.md`
