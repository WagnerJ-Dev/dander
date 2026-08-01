# Morning Handoff

## Finished

- Added recursive `Endpoint.raw_schema` declarations and required them for hosted pipelines.
- Normalized sparse/nested/repeated records and rejected undeclared or invalid values safely.
- Bootstrapped empty BigQuery targets and preserved atomic sandbox replacement through table copy.
- Limited hosted evolution to missing top-level nullable fields; all other deployed drift fails.
- Declared the retained Greenhouse and HubSpot raw schemas without changing GCP or Terraform.

## Try It

- Run `uv run dander validate`.
- Run `uv run pytest tests/test_runtime.py tests/writer/test_bigquery_writer.py`.
- Run `uv run dander run greenhouse_jobs --dry-run --project PROJECT_ID`.

## Checks

- Ruff lint/format and strict mypy pass across source and tests.
- All 550 tests pass; both tracked pipeline dry-runs and `dander validate` pass.
- Terraform format/init/validate pass for root and bootstrap-admin modules.
- Locked dependency audit reports no known vulnerabilities.
- Local container build, CLI/user smoke, and bundled HubSpot asset checks pass.

## Decisions

- Hosted schemas are complete source contracts, not metadata-spine projections.
- Only missing top-level `NULLABLE` fields evolve automatically; nested/type/mode/removal drift fails.
- Legacy direct-source inference remains deprecated compatibility behavior.

## Remaining

- Merge Phase 3 through protected main before starting Phase 4.
- Pre-schema inferred tables may need an operator-reviewed migration before a future live proof.
- No Terraform apply or GCP mutation occurred; none is authorized in this phase.

## Review First

- `src/dander/runtime.py`
- `src/dander/writer/bigquery.py`
- `src/dander/ingestion/source.py`
