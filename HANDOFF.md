# Morning Handoff

## Finished

- Added `dander graph serve --file <graph.yaml>` for one explicit local PipelineGraph file.
- Added canonical GET/conditional-PUT persistence with ETags, validation, atomic replacement, and stale-write rejection.
- Rejects unknown graph fields instead of silently deleting data from a newer graph contract.
- Restricted browser access to an exact configured origin and loopback binding.
- Documented the local visual-editor contract and its intentional execution/deployment boundary.

## Try It

```bash
uv run dander graph serve --file path/to/pipeline.yaml
```

Then open Druff at `http://localhost:3000`, choose **Open from Dander**, edit, and
choose **Save to Dander**.

## Checks

- Ruff check/format and `uv run mypy src tests` — passed for 140 source files.
- `uv run pytest` — 626 passed.
- `pip-audit --strict` — no known vulnerabilities after the two CI-required lock refreshes.
- Focused graph-service tests — 7 passed.
- Browser acceptance — save succeeded, stale save returned conflict without overwrite, restart/reopen succeeded.

## Decisions

- `PipelineGraph` remains canonical; Pydantic 2.12+ rejects unknown fields before the service can normalize them.
- Persistence serves exactly one operator-selected YAML/JSON file with explicit Open/Save.
- This slice stops at local write-back; execution and deployment remain outside the API.

## Remaining

- Review and merge the Dander graph-service PR before treating Druff write-back as generally available.
- Keep the service local-only unless a later authenticated remote design is approved.

## Review First

- `src/dander/pipeline/graph_service.py`
- `tests/pipeline/test_graph_service.py`
- `src/dander/cli/main.py`
