# Morning Handoff

## Finished

- Accepted public `0.1.1rc1` in a fresh billing-linked GCP project without granting the
  installation operator any billing-account IAM role.
- Completed a source-free hosted Greenhouse run: 21 rows, one model, three assertions, successful
  run history, released lease, published metadata, and enabled daily schedule.
- Required exact no-change stage-zero and platform Terraform plans after acceptance.
- Prepared the runtime-identical `0.1.1` promotion metadata.

## Try It

- Run `uv run dander --version`; it should report `dander 0.1.1`.
- Run `uv build` and `uv run python scripts/check_distribution.py dist/*0.1.1*`.

## Checks

- Full suite: 597 passed; Ruff lint/format, strict mypy, and lock validation pass.
- Dependency audit found no known vulnerabilities; Terraform formatting and both roots validate.
- Wheel and sdist inspection, external installation, source-free scaffolding, generated Terraform
  validation, and container startup pass.
- Candidate acceptance passed in `dander-ug-20260802-hco11`; both final Terraform plans reported
  `No changes.`.

## Decisions

- Treat the merged unguarded installation path as a `0.1.x` defect fix, not a new capability.
- Promote the accepted candidate unchanged; any runtime fix requires another candidate.
- Keep `0.1.x` fix-only and continue the existing operator soak on the newest patch.

## Remaining

- Continue the 30-day operator soak in issue #26 on `0.1.1`.
- Review weekly run history and investigate any alert without manually editing leases, watermarks,
  or staging tables.

## Review First

- `CHANGELOG.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
