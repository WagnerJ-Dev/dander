# Morning Handoff

## Finished

- Published and deployed public `dander-platform==0.2.0rc4` as one source-free image across all four retained jobs.
- Completed hosted ServiceNow create, update-ingest, replay, transforms/tests, metadata, and source cleanup; its schedule remains paused.
- Merged protected PR #42 to enable the retained Salesforce daily schedule at 11:00 AM ET.
- Applied an exact one-resource plan changing only the Salesforce scheduler from paused to enabled.
- Observed the first scheduled Salesforce execution complete successfully and preserved the guarded platform.

## Try It

```bash
python -m venv /tmp/dander-rc4
/tmp/dander-rc4/bin/pip install dander-platform==0.2.0rc4
/tmp/dander-rc4/bin/dander --version
```

## Checks

- PR #42: all five protected Python, Terraform/security, distribution, container/scan, and secret checks passed.
- Focused manifest tests: 18 passed; four-pipeline validation and Terraform validation passed.
- Apply: `0 added, 1 changed, 0 destroyed`; only `dander-salesforce-accounts-daily` changed `paused: true -> false`.
- Scheduled run `dander-salesforce-accounts-55rzv`: 13 extracted/affected, one model, four assertions, one metadata asset, status succeeded.
- Salesforce raw/model tables each have 13 unique IDs; zero active leases, no staging residue, and final Terraform plan reports `No changes.`

## Decisions

- ServiceNow v1 uses stable full reads; unsafe timestamp-watermark offset paging remains excluded.
- Salesforce now runs daily at 11:00 AM ET; Greenhouse and HubSpot remain enabled, while ServiceNow remains paused.
- Live planning uses a fresh public-package scaffold overlaid with the retained manifest, connectors, and models so all four pipelines remain represented.

## Remaining

- Continue the operator soak with Greenhouse, HubSpot, and Salesforce enabled.
- Decide separately whether to enable the accepted ServiceNow noon ET schedule.
- Treat NetSuite as a separate connector task; no NetSuite implementation began here.

## Review First

- `dander.yaml`
- `tests/project/test_config.py`
- `tests/cli/test_init_cli.py`
