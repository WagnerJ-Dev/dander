# Morning Handoff

## Finished

- Published and deployed the source-free `0.2.0rc5` graph runtime candidate.
- Ran the retained Greenhouse graph twice through the paused Cloud Run job.
- Verified 21 unique target rows matching raw data exactly after both executions.
- Verified successful run history, released leases, completed-staging cleanup, and unchanged schedules.
- Prepared the version-only `0.2.0` promotion with no `src/dander` or infrastructure changes.

## Try It

```bash
uv run dander --version
uv build
uv run python scripts/check_distribution.py dist/*.whl dist/*.tar.gz
```

## Checks

- Both live graph executions succeeded; 21 target IDs remained unique and raw/target differences were zero.
- Ruff lint/format, strict mypy, and all 636 Python tests passed.
- Both Terraform roots validated; retained stage-zero and platform plans each reported `No changes.`
- Wheel/sdist checks, source-free installs, generated projects, generated Terraform, dependency audit, and local container checks passed.
- Release pre-review approved the eight-file patch and required exact-merge post-CI before tagging.

## Decisions

- Final `0.2.0` changes only release metadata, assertions, notes, and this handoff.
- The accepted `0.2.0rc5` runtime must remain byte-for-byte unchanged under `src/dander`.
- Druff operational controls begin only after final publication, as separate post-release work.

## Remaining

- Run local release validation and prove the accepted runtime tree is unchanged.
- Merge the protected release PR and wait for all five main CI jobs on the exact merge commit.
- Tag and publish `v0.2.0`, then verify a clean public source-free install.
- Implement the narrow Dander validate/run/status API for one bound deployed graph.
- Implement and publish the matching Druff controls without deployment automation.

## Review First

- `CHANGELOG.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
