# Morning Handoff

## Finished

- Added a fail-closed `dander run --sandbox` path for billing-disabled BigQuery projects.
- Added DML-free `WRITE_TRUNCATE` table replacement and empty-snapshot cleanup.
- Added local SQLite cursor state while keeping sandbox extraction as a deterministic full refresh.
- Kept production SCD1, Secret Manager, BigQuery state, and Terraform behavior unchanged.
- Added billing, dataset ordering, writer, state, runtime, and CLI tests.

## Try It

```bash
gcloud auth application-default login
export SECRET_GREENHOUSE='your-test-api-key'
uv run dander run greenhouse --sandbox --project my-no-billing-project
```

Use `--dry-run` first if no Greenhouse test credential is available.

## Checks

- `uv lock` and `uv sync --extra dev` — passed with uv 0.12.0.
- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 301 passed.
- CLI help and sandbox dry-run smoke checks — passed.

## Decisions

- Strict sandbox execution requires an explicit billing-disabled API response.
- Sandbox loads fully replace tables and never use a stored cursor to filter extraction.
- Local SQLite state is diagnostic; the production SCD1 path remains separate.

## Remaining

- Run a live BigQuery Sandbox integration test with user-owned ADC and a Greenhouse test key.
- Stream/chunk large endpoints and add controlled target-schema evolution.
- Add transform execution and metadata-driven tests/catalog publication.
- Add SCD2/snapshot/incremental production writers.
- Provision least-privilege IAM/WIF and Cloud Run for the production path.

## Review First

- `src/dander/runtime.py`
- `src/dander/sandbox.py`
- `src/dander/writer/bigquery.py`
