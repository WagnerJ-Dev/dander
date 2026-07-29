# Morning Handoff

## Finished

- Built the Greenhouse → BigQuery runnable v0 on `codex/dander-v0`.
- Added audited environment/Secret Manager resolution and API-key basic auth.
- Added dlt extraction, idempotent SCD1 staging/MERGE, and post-write BigQuery watermarks.
- Added credential-free `dander run --dry-run` and guarded Terraform plan/apply bootstrap.
- Added 13 runtime tests and corrected the pre-existing Ruff baseline failure.

## Try It

```bash
uv run dander run greenhouse --dry-run --project my-gcp-project
```

Set `SECRET_GREENHOUSE` locally or to a Secret Manager resource, then omit `--dry-run`.

## Checks

- `uv sync --python 3.12 --extra dev` — passed.
- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy` — passed.
- `uv run pytest` — 288 passed.
- CLI help and Greenhouse dry-run smoke checks — passed.
- Terraform 1.9.8 `fmt -check`, `init -backend=false`, and `validate` — passed.

## Decisions

- First runtime slice is Greenhouse/API-key-basic → BigQuery SCD1.
- Response cursor field and request cursor parameter are modeled separately.
- Terraform uses remote GCS state and never applies without explicit confirmation.

## Remaining

- Stream/chunk large endpoints and add controlled target-schema evolution.
- Add transform execution and metadata-driven data tests/catalog publication.
- Add SCD2/snapshot/incremental writers.
- Provision Secret Manager, least-privilege IAM/WIF, and Cloud Run jobs.
- Run a credentialed sandbox integration test before any production claim.

## Review First

- `src/dander/runtime.py`
- `src/dander/ingestion/dlt_backed.py`
- `src/dander/writer/bigquery.py`
