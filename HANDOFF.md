# Morning Handoff

## Finished

- Added a strict executable `PipelineGraph` bridge for existing connector YAML and endpoint bindings.
- Runs graph-selected ingestion and replace-mode BigQuery targets inside the existing history, lease, and heartbeat lifecycle.
- Publishes graph targets through run-scoped staging with creation-time expiry and transactionally fenced replacement.
- Added a source-free Greenhouse graph example to generated projects and container/package assets.
- Preserved existing model pipelines and left all retained live manifests and GCP resources unchanged.

## Try It

```bash
uv run dander init /tmp/dander-graph-demo
uv run dander run greenhouse_jobs --dry-run --project unit-project --config dander.yaml
```

Set a pipeline's `graph` to `graphs/greenhouse_jobs.yaml`, with `models: []` and
`build_models: false`, to activate graph execution for that pipeline.

## Checks

- `uv run pytest` — 636 passed.
- Ruff check/format and `uv run mypy src tests` — passed; 142 source files type-checked.
- `terraform fmt -check -recursive infra` and generated-project `terraform validate` — passed.
- Wheel/sdist build, clean external wheel install, source-free scaffold validation, and container build/dry-run — passed.

## Decisions

- Connector YAML remains authoritative for credentials, requests, pagination, raw schema, and cursor behavior.
- The first runtime slice supports one connector, one or more bound endpoints, compiled transforms, and `replace` targets only.
- Unsupported graph behavior fails before extraction; graph metadata publication remains deferred.

## Remaining

- Review and merge this bridge after the graph-service dependency lands.
- Require explicit approval before pushing an image or adding/deploying a graph pipeline in GCP.
- Extend executable write modes and metadata projection only as separate product work.

## Review First

- `src/dander/pipeline/runtime.py`
- `src/dander/cli/main.py`
- `tests/pipeline/test_runtime_bridge.py`
