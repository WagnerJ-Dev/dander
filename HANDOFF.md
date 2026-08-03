# Morning Handoff

## Finished

- Merged protected PR #39 with the read-only ServiceNow connector, simulator, contract, model, documentation, and paused hosted pipeline.
- Published public `dander-platform==0.2.0rc4` and tag `v0.2.0rc4` after protected PR #40 and five passing CI checks.
- Built and deployed the public package as a source-free image to all four retained Cloud Run jobs.
- Proved hosted ServiceNow create, update-ingest, deterministic replay, transforms, four tests, metadata publication, and source cleanup against the disposable PDI.
- Preserved Greenhouse/HubSpot enabled schedules, Salesforce/ServiceNow paused schedules, all four alerts, and the existing guarded infrastructure.

## Try It

```bash
python -m venv /tmp/dander-rc4
/tmp/dander-rc4/bin/pip install dander-platform==0.2.0rc4
/tmp/dander-rc4/bin/dander --version
```

## Checks

- Local suite: 619 passed; Ruff lint/format, strict mypy, Terraform validation, dependency audit, distributions, source-free install, and Linux image build passed.
- PRs #39 and #40: Python, Terraform/security, distribution, container/scan, and secret checks passed.
- Hosted create/update/replay: three successful runs, each with 68 extracted/affected rows, one model, four assertions, and one metadata asset.
- Replay: 68 raw and modeled rows with 68 unique IDs; zero active leases and no staging residue. The synthetic PDI incident was deleted and verified absent at source.
- Final public-package Terraform plan: `No changes.` All jobs use image digest `sha256:381eafcf...0ed0037`.

## Decisions

- ServiceNow v1 uses stable full reads; unsafe timestamp-watermark offset paging remains excluded.
- ServiceNow stays paused after manual acceptance; enabling its daily noon ET schedule is a separate operator decision.
- SCD1 replay preserves the last accepted destination row after source proof cleanup; source-side deletion propagation is not claimed.

## Remaining

- Decide whether to enable the paused ServiceNow daily schedule after reviewing this acceptance.
- Continue the operator soak on the current public candidate and existing enabled Greenhouse/HubSpot schedules.
- Treat NetSuite as a separate connector task; no NetSuite implementation began here.

## Review First

- `src/dander/sources/servicenow.py`
- `connectors/servicenow.yaml`
- `docs/servicenow.md`
