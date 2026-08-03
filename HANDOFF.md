# Morning Handoff

## Finished

- Added a strict executable `PipelineGraph` bridge for existing connector YAML and endpoint bindings.
- Runs graph-selected ingestion and replace-mode BigQuery targets inside the existing history, lease, and heartbeat lifecycle.
- Publishes graph targets through run-scoped staging with creation-time expiry and transactionally fenced replacement.
- Added a source-free Greenhouse graph example to generated projects and container/package assets.
- Prepared a separate paused `greenhouse_jobs_graph` deployment entry without changing the four
  existing pipeline definitions or any live GCP resource.

## Try It

```bash
uv run dander validate
uv run dander run greenhouse_jobs_graph --dry-run --project unit-project
```

Set a pipeline's `graph` to `graphs/greenhouse_jobs.yaml`, with `models: []` and
`build_models: false`, to activate graph execution for that pipeline.

## Checks

- `uv run pytest` — 636 passed.
- Ruff check/format and `uv run mypy src tests` — passed; 142 source files type-checked.
- `terraform fmt -check -recursive infra` and generated-project `terraform validate` — passed.
- Wheel/sdist build, clean external wheel install, source-free scaffold validation, and container build/dry-run — passed.
- Retained five-pipeline manifest validation and graph deployment dry-run — passed.

## Decisions

- Connector YAML remains authoritative for credentials, requests, pagination, raw schema, and cursor behavior.
- The first runtime slice supports one connector, one or more bound endpoints, compiled transforms, and `replace` targets only.
- Unsupported graph behavior fails before extraction; graph metadata publication remains deferred.

## Remaining

- Review and merge the graph service, runtime bridge, and paused deployment configuration in order.
- Require explicit approval before pushing an image, running a live plan, or deploying the graph pipeline in GCP.
- Extend executable write modes and metadata projection only as separate product work.

## Review First

- `src/dander/pipeline/runtime.py`
- `src/dander/cli/main.py`
- `tests/pipeline/test_runtime_bridge.py`
