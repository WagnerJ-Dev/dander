# Morning Handoff

## Finished

- Added a canonical immutable metadata-spine projection from transform YAML.
- Added deterministic, atomic semantic-registry JSON for agents and local tooling.
- Added Dataplex overview, contacts, schema, and generic system-aspect generation.
- Added a non-deleting, aspect-only `modifyEntry` publisher for BigQuery system entries.
- Added local-first `dander catalog`; cloud publication requires an explicit flag.

## Try It

```bash
uv run dander catalog --project "$PROJECT_ID" \
  --select stg_greenhouse__jobs \
  --output .dander/catalog.json
```

Add `--publish-dataplex --location us --guarded-free-tier` only when accepting metadata-storage
charges. Local output is ignored by Git.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 348 passed.
- `terraform fmt -check -recursive` and `terraform validate` — passed.
- Real Greenhouse registry compile and read-only live Dataplex BigQuery-entry lookup — passed.

## Decisions

- The semantic registry excludes timestamps so identical metadata produces identical bytes.
- Reusable system aspects avoid proprietary aspect-type provisioning.
- Catalog writes are explicit because API calls are free but stored aspect metadata is billable.

## Remaining

- Make `dander init` provision the complete runtime stack through one command.
- Implement idempotent incremental/SCD2/snapshot materializations.
- Execute the visual pipeline mapping/join/custom-code model.
- Prove one concrete hand-rolled enterprise connector.
- Add Harvest v3 credentials only if Greenhouse account access becomes available.

## Review First

- `src/dander/catalog/spine.py`
- `src/dander/catalog/dataplex.py`
- `docs/spec-alignment.md`
