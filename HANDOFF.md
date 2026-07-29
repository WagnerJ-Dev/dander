# Morning Handoff

## Finished

- Created isolated GCP project `dander-sbx-harrison-20260729` and linked billing.
- Created project-scoped `dander-sbx-cap`: $5 USD with 80%/100% current-spend thresholds.
- Deployed the Pub/Sub/Eventarc billing kill switch in `us-central1`.
- Simulation produced `simulated-disable`; live mode is active with retries and zero min instances.
- Added tested, deployable function source and provider-managed subscription support.

## Try It

```bash
uv run dander run greenhouse --guarded-free-tier --dry-run \
  --project dander-sbx-harrison-20260729
```

The live run still needs a Greenhouse test API key stored in Secret Manager.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 312 passed.
- Synthetic `$6/$5` event in simulation mode — `simulated-disable`.
- Live guarded preflight — passed; final billing status remains enabled.

## Decisions

- The live handler is budget-specific, idempotent, retrying, and deployed simulation-first.
- Runtime identity has billing-project-manager, Eventarc receiver, and log-writer roles.
- Eventarc alone can invoke the private Cloud Run service.

## Remaining

- Add a Greenhouse test key to Secret Manager and run the credentialed ingestion.
- Create the GCS Terraform-state bucket and apply the BigQuery bootstrap.
- Review or remove default project service accounts with broad Editor grants.
- Stream/chunk large endpoints and add controlled target-schema evolution.
- Add transform execution and metadata-driven tests/catalog publication.

## Review First

- `infra/functions/stop_billing/handler.py`
- `infra/functions/stop_billing/main.py`
- `src/dander/sandbox.py`
