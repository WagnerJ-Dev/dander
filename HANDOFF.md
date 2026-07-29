# Morning Handoff

## Finished

- Added `dander run --guarded-free-tier` for billing-linked production-path testing.
- Preflight requires billing enabled and a project-scoped USD budget no greater than $5.
- Preflight requires 80%/100% current-spend thresholds plus conventional Pub/Sub wiring.
- Kept the strict no-billing sandbox and unguarded production composition unchanged.
- Documented free allowances, trial behavior, delayed billing, shutdown, and recovery risks.

## Try It

```bash
uv run dander run greenhouse --guarded-free-tier --dry-run --project my-project
```

After deploying the documented budget handler, omit `--dry-run` and point
`SECRET_GREENHOUSE` at its Secret Manager version.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 308 passed.
- CLI help and guarded-mode dry-run smoke checks — passed.
- `git diff --check` — passed.

## Decisions

- Budgets and kill switches are guardrails, never described as guaranteed caps.
- Guarded mode verifies configuration before any credentials or source activity.
- Passing guarded preflight uses the existing production SCD1 and managed-state path.

## Remaining

- Deploy and test the kill-switch handler in a dedicated disposable GCP project.
- Run live strict-sandbox and guarded-mode integrations with user-owned credentials.
- Stream/chunk large endpoints and add controlled target-schema evolution.
- Add transform execution and metadata-driven tests/catalog publication.
- Provision least-privilege IAM/WIF and Cloud Run for production.

## Review First

- `src/dander/sandbox.py`
- `src/dander/cli/main.py`
- `src/dander/writer/bigquery.py`
