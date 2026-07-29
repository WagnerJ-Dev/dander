# Morning Handoff

## Finished

- Added a credential-free Greenhouse Job Board connector using published jobs.
- Upgraded canonical private Greenhouse ingestion to Harvest v3 OAuth client credentials.
- Added audited secret resolution, bearer caching/refresh, response selectors, and dlt auth bridging.
- Preserved Harvest v1 under an explicitly temporary legacy connector.
- Kept the live `$5` GCP guard active and billing enabled.

## Try It

```bash
uv run dander run greenhouse_job_board --guarded-free-tier --dry-run \
  --project dander-sbx-harrison-20260729
```

Remove `--dry-run` after the BigQuery dataset bootstrap to ingest public jobs without a credential.
Private `greenhouse` runs require Harvest v3 client ID and client secret references.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 322 passed.
- Read-only live public extraction — 21 Greenhouse jobs returned.
- Public and Harvest v3 CLI dry runs — passed without credentials.

## Decisions

- Public Job Board and private Harvest are distinct connectors and data-access boundaries.
- Harvest v3 OAuth is canonical; v1 is compatibility-only until its 2026-08-31 shutdown.
- The dlt adapter applies auth per request so cached tokens can refresh across pagination.

## Remaining

- Create the GCS Terraform-state bucket and apply the BigQuery bootstrap.
- Run the public connector through the guarded BigQuery write path.
- Add Harvest v3 credentials only if Greenhouse account access becomes available.
- Review or remove default project service accounts with broad Editor grants.
- Stream/chunk large endpoints and add controlled target-schema evolution.

## Review First

- `connectors/greenhouse_job_board.yaml`
- `src/dander/security/oauth.py`
- `src/dander/ingestion/dlt_backed.py`
