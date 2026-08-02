# Morning Handoff

## Finished

- Prepared `0.1.1rc1` from the merged optional-cost-guard fix with no `src/dander` change.
- Updated only package version assertions, the lockfile, release notes, and this handoff.
- Built and inspected the candidate wheel and source distribution.
- Installed both artifacts outside the checkout and generated valid source-free projects.

## Try It

- Run `uv run dander --version`; it should report `dander 0.1.1rc1`.
- Run `uv build` and `uv run python scripts/check_distribution.py dist/*0.1.1rc1*`.

## Checks

- Full suite: 597 passed; Ruff lint/format, strict mypy, and lock validation pass.
- Dependency audit found no known vulnerabilities; Terraform formatting and both roots validate.
- Wheel and sdist inspection, external installation, source-free scaffolding, generated Terraform
  validation, and container startup pass.

## Decisions

- Treat the merged unguarded installation path as a `0.1.x` defect fix, not a new capability.
- Prove the candidate in a fresh billing-linked project using an operator identity with no
  billing-account IAM role.
- Promote the accepted candidate unchanged; any runtime fix requires another candidate.

## Remaining

- Merge the candidate PR through protected `main`, then tag and publish `v0.1.1rc1`.
- Complete one source-free unguarded Greenhouse installation and require a clean final plan.
- Promote the unchanged candidate to `0.1.1` and continue operator-soak issue #26.

## Review First

- `CHANGELOG.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
