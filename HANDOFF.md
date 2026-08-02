# Morning Handoff

## Finished

- Reused `require_guarded_free_tier` and the existing cost-guard CLI flags so the resolved safety
  setting controls the default without adding another installation mode or manifest field.
- Made unguarded hosted initialization accept no billing-account ID and omit billing-account IAM,
  cost-guard resources, guard-specific Pub/Sub access, runtime billing viewer, and runtime preflight.
- Preserved the guarded path and conditioned only Cloud Functions/Pub/Sub bootstrap permissions that
  exist for the managed guard.
- Changed generated projects to default unguarded and updated the hosted quickstart with the billing
  and spending warning; the retained repository manifest remains explicitly guarded.
- Added focused regression coverage for CLI resolution, stage zero, Terraform rendering, scaffold
  output, ordinary hosted resources, and guarded compatibility.

## Try It

- Run `uv run dander new /tmp/dander-optional` and inspect its `dander.yaml`.
- Run `uv run pytest tests/cli/test_init_cli.py tests/bootstrap/test_terraform.py tests/infra`.

## Checks

- Focused suite: 67 passed. Full suite: 597 passed.
- Ruff lint/format, strict mypy, dependency audit, Terraform format, and diff checks pass.
- Repository, generated-source, wheel, and sdist Terraform roots initialize with backends disabled
  and validate; wheel/sdist inspection, external installation, scaffolding, and container startup pass.
- Retained stage-zero and platform Terraform plans each report exactly `No changes.`

## Decisions

- Generated manifests explicitly default to unguarded while the model default remains guarded for
  compatibility with existing manifests that omit the safety field.
- Billing input is passed to stage zero and platform Terraform only when the managed guard is enabled.
- Runtime billing and Pub/Sub visibility follows the guarded-runtime setting, not general ingestion.

## Remaining

- Review the focused pull request; do not merge it without separate approval.
- Treat any deliberate change from guarded to unguarded on an existing install as a normal reviewed
  Terraform removal plan.

## Review First

- `src/dander/cli/main.py`
- `infra/bootstrap-admin/main.tf`
- `infra/modules/scheduled-job/main.tf`
