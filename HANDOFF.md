# Morning Handoff

## Finished

- Published runtime-identical Salesforce and ServiceNow `0.1.1` packages compatible with Dander
  `0.4.x` and `0.5.x`.
- Added a static curated catalog for those two provider-validated first-party alpha connectors.
- Added `dander plugins search` with exact public package pins and compatibility/support status.
- Added `GET /v1/plugin-catalog` while leaving installed runtime discovery unchanged.
- Derived installed markers only from validated, manifest-declared plugins.

## Try It

```bash
uv run dander plugins search
uv run dander plugins search incident
```

## Checks

- Full suite: 713 tests passed; Ruff lint/format and strict mypy across 162 source files passed.
- Focused catalog/CLI/graph-service suite: 23 tests passed.
- Dependency audit found no known vulnerabilities.
- Terraform formatting, backend-disabled initialization, and both module validations passed.
- Wheel and sdist built in a clean directory and passed distribution inspection.
- Local Linux container build, CLI startup, and unprivileged runtime-user check passed.

## Decisions

- Keep discovery static and package-backed; no marketplace service or runtime PyPI query.
- Keep package installation and manifest changes explicit operator actions.
- Preserve `/v1/connectors` as active runtime metadata and use `/v1/plugin-catalog` for discovery.

## Remaining

- Merge the Dander PR through protected CI before opening the dependent Druff PR.
- Merge the Druff PR only after the accepted Dander API contract is on `main`.
- Do not version, publish, deploy, or change the retained GCP project in this slice.

## Review First

- `src/dander/plugins/catalog.py`
- `src/dander/pipeline/graph_service.py`
- `tests/plugins/test_catalog.py`
