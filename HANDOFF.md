# Morning Handoff

## Finished

- Deployed the exact source-free `0.2.0rc1` image to the retained proof project with all three schedules paused.
- Added the paused Salesforce hosted resources and two enabled secret versions; the reviewed apply was 17 added, 4 changed, 0 destroyed.
- Passed Greenhouse and HubSpot hosted smoke runs on `0.2.0rc1`.
- Captured Salesforce's `Decimal is not JSON serializable` failure and verified zero rows, no cursor, no lease, and no staging residue.
- Fixed BigQuery JSON-load encoding for validated decimal and temporal values, including nested data.

## Try It

```bash
uv run pytest tests/writer/test_bigquery_writer.py
uv run pytest
```

## Checks

- Writer regression suite: 34 passed; full suite: 611 passed.
- Ruff lint/format, strict mypy, lock validation, and both Terraform roots passed.
- Retained stage-zero plan before rollout: `No changes`.
- Immediate all-paused post-apply platform plan: `No changes`.
- Salesforce failure cleanup queries found 0 raw rows and no watermark, lease, or staging table.

## Decisions

- Keep every scheduler paused until a corrected release candidate completes the hosted smoke suite.
- Convert typed scalars only at the BigQuery JSON-load boundary; retain source and schema typing.
- Replace failed `0.2.0rc1` with `0.2.0rc2` before rerunning Salesforce.

## Remaining

- Merge the focused writer-fix PR through protected CI.
- Prepare, approve, and publish version-only `0.2.0rc2`.
- Build and deploy a source-free rc2 image while all schedules remain paused.
- Rerun Greenhouse, HubSpot, and Salesforce, then replay Salesforce once.
- Restore Greenhouse and HubSpot schedules and require a final no-drift plan.

## Review First

- `src/dander/writer/bigquery.py`
- `tests/writer/test_bigquery_writer.py`
- `HANDOFF.md`
