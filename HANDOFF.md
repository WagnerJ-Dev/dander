# Morning Handoff

## Finished

- Added a read-only ServiceNow incident connector with OAuth client credentials, declared raw schema, primitive values, and stable full-read pagination.
- Added a stateful FastAPI simulator, realistic multi-page fixtures, a seven-operation OpenAPI contract, and named auth, throttling, permission, and malformed-record failures.
- Added the staging model, metadata/tests, setup guide, limitations, and a paused hosted ServiceNow pipeline definition.
- Configured the disposable PDI and proved token exchange, read, create, update-ingest, deterministic replay, and proof-object cleanup.
- Kept all existing pipeline schedules and deployed GCP resources unchanged during connector development.

## Try It

```bash
uv run python -m dander.dev.servicenow_simulator
uv run pytest tests/integration/test_servicenow_simulator.py
```

## Checks

- Focused ServiceNow and manifest suite: 35 passed.
- Full suite: 619 passed; Ruff lint/format and strict mypy passed.
- Terraform root and stage-zero initialization/validation passed; `dander validate` found four additive pipelines.
- Dependency audit reported no known vulnerabilities; wheel/sdist inspection passed.
- Local Linux container built, started the CLI, and contained the ServiceNow connector and model.

## Decisions

- Use stable full reads in v1; timestamp watermarks plus offset paging could skip moving records.
- Keep ServiceNow paused after provisioning until the hosted create/update/replay proof passes.
- Treat source hard-delete propagation and keyset incrementality as explicit later work.

## Remaining

- Complete the final adversarial review and merge the focused feature PR through protected main.
- Publish `0.2.0rc4` from a separate release PR.
- Add the two credential values to Secret Manager, apply the reviewed additive paused plan, and run hosted ServiceNow create/update/replay/cleanup acceptance.
- Verify existing schedules, alerts, leases, staging cleanup, run history, and a final no-drift Terraform plan.

## Review First

- `connectors/servicenow.example.yaml`
- `src/dander/dev/servicenow_simulator.py`
- `tests/integration/test_servicenow_simulator.py`
