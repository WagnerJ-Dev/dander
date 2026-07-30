# Morning Handoff

## Finished

- Integrated the tested billing handler into the reviewed Terraform bootstrap.
- Added a project-only USD budget, 80%/100% thresholds, Pub/Sub, and Gen 2 function.
- Added dedicated runtime/build identities and the documented Gen 2 build permissions.
- Extended `dander init` with simulation-first cost-guard controls and explicit live-mode warning.
- Preserved a literal no-change plan for the deployed sandbox when the module is disabled.

## Try It

```bash
uv run dander init --project PROJECT --state-bucket BUCKET \
  --billing-account ABCDEF-123456-ABCDEF --enable-cost-guard
```

This only plans and keeps billing detachment simulated. Do not add `--live-cost-guard --apply`
until simulation logs are verified and destructive billing unlinking is genuinely intended.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 365 passed.
- `terraform fmt -recursive -check` and `terraform validate` — passed.
- Live disabled plan: no changes; opt-in simulation plan: 23 adds, 0 changes, 0 destroys.

## Decisions

- The guard is opt-in and simulation-first; live mode is separately explicit.
- Budget API quota-project routing is isolated from ordinary Terraform refreshes.
- A budget is delayed automation, never described as a hard spending ceiling.

## Remaining

- Import existing manually created guard resources before managing this sandbox with the new module.
- Implement incremental, SCD2, and snapshot materializations.
- Execute visual mapping/join/custom-code pipeline definitions.
- Prove a concrete hand-rolled enterprise connector.
- Complete the release audit and external legal gate.

## Review First

- `infra/modules/cost-guard/main.tf`
- `src/dander/bootstrap/terraform.py`
- `tickets/DANDER-29-integrated-cost-guard.md`
