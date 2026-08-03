# Morning Handoff

## Finished

- Published and source-free verified `dander-platform==0.2.0rc1` from protected `main`.
- Added a concrete read-only Salesforce Accounts connector for the disposable Developer Edition org.
- Added the retained project's Salesforce pipeline, dedicated identities, secret references, and 11:00 ET schedule in a paused state.
- Built and validated a local source-free candidate image containing all three retained pipelines.
- Prepared read-only retained-project plans; no Terraform apply or GCP mutation occurred.

## Try It

```bash
uv run dander validate --config dander.yaml
docker run --rm dander-v020rc1-salesforce:local validate
uv run pytest
```

## Checks

- Focused configuration tests: 18 passed; full suite: 610 passed.
- Ruff lint/format, strict mypy, lock validation, `git diff --check`, and both Terraform roots passed.
- Local source-free image reports `0.2.0rc1`, runs non-root, imports Dander from site-packages, and validates three pipelines.
- Retained stage-zero plan: `No changes`.
- Retained all-paused platform plan: 17 additions, 2 scheduler pauses, 0 deletions.

## Decisions

- Keep Salesforce paused until its authenticated hosted proof passes.
- Upgrade the shared image only while Greenhouse and HubSpot schedules are paused.
- Keep image publication, secret writes, and Terraform apply behind separate explicit approval.

## Remaining

- Merge the focused hosted-configuration PR through protected CI.
- Obtain approval to push the exact source-free candidate image and apply the reviewed paused plan.
- Add the two Salesforce secret versions without printing their values.
- Smoke-test Greenhouse, HubSpot, and Salesforce, then restore only Greenhouse and HubSpot schedules.
- Require a final no-drift Terraform plan.

## Review First

- `connectors/salesforce.yaml`
- `dander.yaml`
- `infra/sandbox.auto.tfvars.example`
