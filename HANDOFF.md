# Morning Handoff

## Finished

- Streamed hosted SCD1 extraction in `platform.runtime.batch_rows` batches.
- Delayed endpoint watermark commits until every SCD1 batch succeeds.
- Made sandbox replace stage bounded batches and publish only after complete extraction.
- Added deterministic cross-batch overwrite, failure cleanup, and 100,003-row regression coverage.
- Left SCD2, snapshot, incremental-writer, Storage Write, Terraform, and GCP behavior unchanged.

## Try It

- Run `uv run pytest tests/test_runtime.py tests/writer/test_bigquery_writer.py`.
- Run `uv run dander run greenhouse_jobs --dry-run --project PROJECT_ID`.

## Checks

- Focused runtime, writer, and CLI tests pass.
- Ruff lint/format pass and strict mypy passes across 119 source files.
- All 522 tests pass.

## Decisions

- SCD1 publishes batches idempotently; a later failure is repaired by replay before watermark advance.
- Replace alone uses one endpoint-scoped staging table to retain atomic publication.
- Other writer modes do not become streaming-capable in Phase 2.

## Remaining

- Merge Phase 2 through protected main before starting schema-reality work.
- Phase 3 must remove the empty-source synthetic-seed requirement.
- No Terraform apply or GCP mutation is authorized.

## Review First

- `src/dander/runtime.py`
- `src/dander/writer/bigquery.py`
- `tests/test_runtime.py`
