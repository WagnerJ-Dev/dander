# Morning Handoff

## Finished

- Published `0.2.0rc2` from protected `main` and verified the public wheel and source distribution outside the checkout.
- Built and applied the public source-free rc2 image to all three retained Cloud Run jobs; all schedules remain paused.
- Confirmed the rc2 Salesforce run failed safely because BigQuery rejected Salesforce's valid `+0000` timestamp offset.
- Fixed declared TIMESTAMP normalization to emit typed, canonical values and canonical ISO 8601 watermarks.
- Added regression assertions using the exact Salesforce timestamp format that failed live.

## Try It

```bash
uv run pytest tests/test_runtime.py tests/writer/test_bigquery_writer.py -q
uv run pytest
```

## Checks

- Focused runtime/writer suite: 60 passed.
- Full suite: 611 passed; Ruff lint/format, strict mypy, and lock validation passed.
- Locked dependency audit found no known vulnerabilities.
- Wheel/sdist inspection, external install/scaffold, and both backend-disabled Terraform validations passed.
- Failed live run left zero Salesforce rows, no watermark, a released lease, and no staging table.

## Decisions

- Treat rc2 as failed acceptance; do not promote it.
- Keep the timestamp repair provider-agnostic and limited to the existing raw-schema boundary.
- Require separate approval before publishing the corrected candidate.

## Remaining

- Merge the focused timestamp fix through protected CI.
- Prepare and obtain approval for `0.2.0rc3`.
- Deploy the public rc3 source-free image and complete Salesforce ingestion plus replay.
- Reverify rows, transforms/tests, watermark monotonicity, cleanup, and Terraform drift.
- Restore retained scheduler state only after candidate acceptance is complete.

## Review First

- `src/dander/runtime.py`
- `tests/test_runtime.py`
- `HANDOFF.md`
