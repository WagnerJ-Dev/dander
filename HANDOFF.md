# Morning Handoff

## Finished

- Added explicit `unique_key` and `incremental_cursor` transform metadata.
- Added create-if-absent plus watermark-bounded BigQuery incremental `MERGE`.
- Added deterministic per-key deduplication at tied cursor boundaries.
- Added fail-before-query validation for absent or undeclared incremental columns.
- Preserved existing view/table builds and post-build generic assertions.

## Try It

Set `materialization: incremental`, `unique_key: [id]`, and `incremental_cursor: updated_at` in a
model sidecar, then run:

```bash
uv run dander build --project "$PROJECT_ID" --select MODEL --guarded-free-tier
```

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 374 passed.
- `terraform fmt -recursive -check` and `terraform validate` — passed.

## Decisions

- Incremental keys/cursors are explicit metadata, never inferred.
- The max-cursor boundary is inclusive so tied timestamps cannot be lost.
- Canonical JSON provides deterministic tie-breaking; key merge makes boundary rereads idempotent.

## Remaining

- Dispatch visual target-node writer configuration into concrete writers.
- Add bounded chunk loading and controlled schema evolution.
- Execute visual mapping/join/custom-code pipeline definitions.
- Prove a concrete hand-rolled enterprise connector.
- Add hosted transform/catalog scheduling and run history.

## Review First

- `src/dander/transform/runner.py`
- `src/dander/transform/config.py`
- `tests/transform/test_runner.py`
