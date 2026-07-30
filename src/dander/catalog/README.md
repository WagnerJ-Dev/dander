# Metadata spine and catalog

The catalog package projects the same validated model YAML used by the transform engine into two
additional representations:

- a deterministic, versioned JSON semantic registry for agents and local tooling;
- Dataplex Knowledge Catalog system aspects for overview, contacts, schema, and generic metadata.

Local compilation is the default and requires no catalog API:

```bash
uv run dander catalog \
  --project "$PROJECT_ID" \
  --select stg_greenhouse__jobs \
  --output .dander/catalog.json
```

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
