# Transform engine

Dander owns the SQL transform layer described in the project decision log. A project is a directory
of BigQuery SQL files with same-named YAML sidecars. The sidecar is the metadata spine shared by
execution, generic tests, future Dataplex aspects, and the semantic registry.

## Build contract

1. Discover every `*.sql` file and validate its `*.yml` or `*.yaml` sidecar.
2. Resolve model `ref()` calls and conventional `raw_<table>` source references.
3. Reject unknown references and cycles before submitting a query.
4. Render refs through a restricted Jinja environment and require one read-only BigQuery query.
5. Materialize selected models and their dependencies as views or tables in topological order.
6. Run declared not-null, unique, accepted-values, and relationship assertions.

```bash
uv run dander build --project "$PROJECT_ID" --select stg_greenhouse__jobs
uv run dander test --project "$PROJECT_ID" --select stg_greenhouse__jobs
```

`build` materializes and tests; `test` only evaluates existing relations. Both commands accept
`--guarded-free-tier`. Incremental materialization is deliberately rejected until it can reuse a
fully specified idempotent writer contract.
