# Morning Handoff

## Finished

- Added optional immutable Druff image input to normal initialization and full-platform previews.
- Added a public, scale-to-zero Cloud Run UI beside the hosted runtime with a dedicated no-role
  service account and one Terraform owner for Cloud Run API enablement.
- Kept graph persistence, connector data, credentials, and execution on Dander's loopback service.
- Packaged the new Terraform module into generated source-free projects.
- Documented exact image retention, public usage, and local-network behavior.

## Try It

```bash
uv run dander init --project PROJECT --container-image DANDER_DIGEST \
  --druff-container-image DRUFF_DIGEST
uv run dander graph serve --file /path/to/graph.yaml --origin HTTPS_DRUFF_URL
```

## Checks

- Full suite: 717 tests passed; Ruff and strict mypy across 163 source files passed.
- Dependency audit found no known vulnerabilities.
- Terraform format/init/validation passed for the platform, stage zero, and packaged project.
- Wheel and sdist inspection plus two outside-checkout installs/scaffolds passed.
- Dander container build/start/non-root checks passed; Docker Scout found 0 fixed high/critical issues.

## Decisions

- Host only Druff's compiled browser shell; never publish Dander's unauthenticated graph API.
- Use one explicit digest input rather than adding a manifest mode or UI backend.
- Preserve the image in Druff-triggered full-platform previews to prevent accidental removal plans.

## Remaining

- Pass protected CI in both repositories; final adversarial review is already clean.
- Merge Druff first, then Dander.
- Push the immutable Druff image to the disposable proof project.
- Apply only the reviewed Druff additions and verify the hosted-to-local bridge.
- Confirm paused schedules and a final no-drift Terraform plan; never touch the retained project.

## Review First

- `infra/modules/druff/main.tf`
- `src/dander/bootstrap/terraform.py`
- `src/dander/pipeline/graph_deployment.py`
