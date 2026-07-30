# Morning Handoff

## Finished

- Added typed SQL-model/YAML discovery with fail-closed metadata validation.
- Added dependency ordering, restricted `ref()` compilation, and read-only BigQuery SQL checks.
- Added view/table materialization plus four generic data-test kinds.
- Added `dander build` and `dander test` with selection and guarded-free-tier support.
- Built `staging.stg_greenhouse__jobs` live with 21 unique, non-null public jobs.

## Try It

```bash
uv run dander build --project "$PROJECT_ID" \
  --select stg_greenhouse__jobs --guarded-free-tier
uv run dander test --project "$PROJECT_ID" \
  --select stg_greenhouse__jobs --guarded-free-tier
```

Repeat `--select` for multiple roots; omit it to build all discovered models.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 338 passed.
- `terraform fmt -check -recursive` and `terraform validate` — passed.
- Guarded live build/test — 3 assertions passed; 21 rows, 21 unique ids, zero null ids.

## Decisions

- `raw_<table>` refs map conventionally to raw relations; all other refs name discovered models.
- Transform SQL must compile to one read-only query before Dander wraps it in controlled DDL.
- Incremental materialization fails closed until it has an explicit idempotent write contract.

## Remaining

- Project the model YAML into Dataplex aspects and a local semantic manifest.
- Make `dander init` provision the complete runtime stack through one command.
- Implement idempotent incremental/SCD2/snapshot materializations.
- Add Harvest v3 credentials only if Greenhouse account access becomes available.
- Stream/chunk large endpoints and add controlled target-schema evolution.

## Review First

- `src/dander/transform/project.py`
- `src/dander/transform/runner.py`
- `models/staging/stg_greenhouse__jobs.yml`
