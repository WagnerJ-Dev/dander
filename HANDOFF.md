# Morning Handoff

## Finished

- Added an injected run-history state interface.
- Persisted cloud/guarded runs to a parameterized BigQuery control table.
- Persisted sandbox runs beside watermarks in the existing SQLite file.
- Recorded running, succeeded, and failed lifecycle states with aggregate counts.
- Kept rows, cursors, credentials, and exception text out of history.

## Try It

Run any connector normally. Inspect `_dander_runs` in the raw BigQuery dataset, or the `runs`
table in `.dander/state.db` when using `--sandbox`.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed across 85 source files.
- `uv run pytest` — 413 passed.
- `git diff --check` — passed.
- Secret-pattern scan found only its intentional private-key detector fixture.

## Decisions

- History is required in CLI execution but remains optional for library callers.
- Terminal records aggregate only completed endpoints.
- History failure never masks an existing pipeline failure.

## Remaining

- Add bounded writer loads and controlled nested schema evolution.
- Add hosted transform/catalog scheduling.
- Complete the release audit and external legal gate.

## Review First

- `src/dander/state/run_history.py`
- `src/dander/runtime.py`
- `docs/spec-alignment.md`
