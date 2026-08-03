# Morning Handoff

## Finished

- Merged protected PR #39 with the read-only ServiceNow connector, simulator, contract, staging model, documentation, and paused hosted pipeline.
- Proved OAuth token exchange and a 67-row primitive incident read against the disposable PDI.
- Proved synthetic create, update-ingest, deterministic replay, and source proof-object cleanup without retaining synthetic data.
- Passed final independent adversarial review and all five protected CI checks.
- Prepared `0.2.0rc4` as a release-only change over merged ServiceNow main.

## Try It

```bash
uv run dander --version
uv build
uv run python scripts/check_distribution.py dist/*.whl dist/*.tar.gz
```

## Checks

- Local full suite: 619 passed; Ruff lint/format and strict mypy passed.
- Terraform root and stage-zero validation passed; `dander validate` found four additive pipelines.
- Dependency audit, wheel/sdist inspection, source-free wheel install, and local Linux container checks passed.
- PR #39 CI: Python, Terraform/security, distribution, container/scan, and secret checks passed.
- Live PDI replay ended with 67 unique records and no synthetic proof record.

## Decisions

- ServiceNow v1 uses stable full reads; unsafe timestamp-watermark offset paging is excluded.
- The hosted ServiceNow schedule stays paused until manual hosted acceptance passes.
- `0.2.0rc4` changes release metadata only after the accepted connector merge.

## Remaining

- Merge the release PR through protected CI, then tag and publish `v0.2.0rc4`.
- Build the exact public package into a source-free image.
- Add ServiceNow credentials to the existing secret containers and apply the reviewed additive paused plan.
- Run hosted create/update/replay/cleanup acceptance and verify run history, rows, tests, metadata, leases, staging, alerts, existing schedules, and final no drift.

## Review First

- `CHANGELOG.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
