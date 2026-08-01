# Metadata spine and catalog

The catalog package projects the same validated model YAML used by the transform engine into three
additional representations:

- an atomic BigQuery/SQLite pipeline snapshot containing source, model, lineage, test, and metric
  definitions;
- a deterministic, versioned JSON semantic registry for agents and local tooling;
- Dataplex Knowledge Catalog system aspects for overview, contacts, schema, and generic metadata.

Local compilation is the default and requires no catalog API:

```bash
uv run dander catalog \
  --project "$PROJECT_ID" \
  --select stg_greenhouse__jobs \
  --output .dander/catalog.json
```

Named pipelines publish the durable snapshot automatically only after ingestion, transforms, and
tests succeed. Inspect it with:

```bash
uv run dander metadata list --project "$PROJECT_ID"
uv run dander metadata metrics --project "$PROJECT_ID"
uv run dander metadata runs --project "$PROJECT_ID"
```

Each model metric declares its name, definition, aggregation, and governed field in the same YAML
sidecar; the spine emits the resulting calculation (for example `SUM(arr_amount)`) without
executing arbitrary authored SQL.

Cloud mutation requires an explicit flag:

```bash
uv run dander catalog \
  --project "$PROJECT_ID" \
  --select stg_greenhouse__jobs \
  --publish-dataplex \
  --location us \
  --guarded-free-tier
```

The publisher uses `modifyEntry` for the first-party BigQuery system entry, updates only the four
generated aspect keys, and leaves unrelated aspects untouched. It does not create custom aspect
types. Dataplex API calls are free, but Google charges for stored aspect metadata; see the current
[Knowledge Catalog pricing](https://cloud.google.com/products/knowledge-catalog/pricing).
Therefore Dander never publishes merely because `catalog` was run.
