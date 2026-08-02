# Morning Handoff

## Finished

- Published public `0.1.0rc7` and deployed its source-free image to the retained project.
- Passed simultaneous Greenhouse/HubSpot execution with isolated leases and no task retries.
- Passed Greenhouse replay, authenticated HubSpot create/update/replay/cleanup, and same-pipeline
  skip/success overlap with stable hashes, cursors, and duplicate-free tables.
- Verified clear leases, cleaned staging, staging expiration, enabled alerts, and restored schedules.
- Finished with a no-drift Terraform plan and preserved the independent fresh-project proof.

## Try It

- Run `uv run pytest` and `uv run dander --version`.
- Build with `uv build`, install outside the checkout, and run `dander new` plus Terraform validate.

## Checks

- All 594 tests, Ruff lint/format, strict mypy, dependency audit, and lock validation pass.
- Public wheel/sdist installation and source-free scaffold validation pass.
- Retained live acceptance and final Terraform no-drift reconciliation pass.

## Decisions

- Promote the tested rc7 runtime unchanged; the final PR changes only version/release records.
- Keep the historical shared lease table untouched; per-pipeline tables are the active control path.
- Begin the 30-day operator soak only after the public `0.1.0` smoke succeeds.

## Remaining

- Merge the final version-only PR through protected main.
- Tag and publish `v0.1.0` through the protected PyPI environment.
- Verify public installation, generated project, final image update, Greenhouse smoke, and no drift.
- Create the alpha GitHub Release and open the single operator-soak issue.

## Review First

- `CHANGELOG.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
