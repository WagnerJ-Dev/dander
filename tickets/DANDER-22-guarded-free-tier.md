# DANDER-22 — Billing-linked guarded free-tier mode

Status: done

## Context

A billing-linked project can exercise Dander's production Secret Manager, Terraform, BigQuery
DML, and remote-state path while remaining inside monthly free usage. Billing budgets are alerts,
not spending caps, and their notifications can lag. Dander must not describe this as guaranteed
cost containment.

## Acceptance criteria

- `dander run --guarded-free-tier` is mutually exclusive with `--sandbox`.
- Preflight requires billing enabled for the selected project.
- Preflight requires a project-scoped USD budget named `dander-sbx-cap`, no greater than $5.
- The budget has current-spend thresholds at 80% and 100% and publishes to the conventional
  `dander-stop-billing` Pub/Sub topic.
- That topic has the conventional `dander-stop-billing` subscription attached.
- Preflight failures happen before source credentials, extraction, or writes.
- A passing preflight uses the existing production SCD1, Secret Manager, and BigQuery state path.
- Tests use fakes and make no GCP calls.
- Documentation states that notifications lag and no hard cap is guaranteed.

## Review

PASS — preflight is mutually exclusive with strict sandbox mode and executes before credential
resolution. It requires an enabled billing link, fixed <=$5 project budget, current-spend
thresholds, topic, and subscription; it then preserves the production composition. Documentation
does not claim a hard cap. Ruff, formatting, strict mypy, 308 tests, CLI help, guarded dry-run, and
diff checks pass.
