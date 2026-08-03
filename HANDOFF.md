# Morning Handoff

## Finished

- Published and source-free deployed `0.2.0rc2`; its Salesforce acceptance run exposed a timestamp serialization defect.
- Verified the failed run published no rows or watermark and left no active lease or staging table.
- Merged the provider-agnostic timestamp repair through protected PR #36 with all five checks passing.
- Prepared `0.2.0rc3` as a version-only candidate over that repaired runtime.

## Try It

```bash
uv run dander --version
uv build --out-dir /tmp/dander-v020rc3
uv run python scripts/check_distribution.py /tmp/dander-v020rc3/*.whl /tmp/dander-v020rc3/*.tar.gz
```

## Checks

- Timestamp repair: focused 60 passed; full 611 passed; Ruff, mypy, lock, audit, and Terraform validations passed.
- Protected PR #36: Python, Terraform, distribution, container/scan, and secret checks passed.
- rc3 candidate: full 611 passed; Ruff, mypy, lock, artifact inspection, external source-free install/scaffold, and generated Terraform validation passed.

## Decisions

- Treat rc2 as failed acceptance and do not promote it.
- Keep rc3 version-only relative to repaired `main`; do not change `src/dander`.
- Require explicit approval before tagging or publishing rc3.

## Remaining

- Merge the rc3 candidate through protected CI.
- Obtain explicit approval, then tag and publish `0.2.0rc3`.
- Deploy the exact public source-free rc3 image and complete Salesforce ingestion plus replay.
- Verify rows, transforms/tests, run history, monotonic watermark, cleanup, and Terraform drift.
- Restore retained scheduler state only after candidate acceptance is complete.

## Review First

- `CHANGELOG.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
