# Morning Handoff

## Finished

- Prepared `0.2.0rc1` from merged `main` as Dander's next alpha capability candidate.
- Updated only package/scaffold version assertions, lock metadata, release notes, and this handoff.
- Included the already merged Salesforce Accounts slice and Workday simulator in candidate notes.
- Built and inspected the wheel/sdist, then installed and scaffolded from both outside the checkout.

## Try It

```bash
uv run dander --version
uv build --out-dir /tmp/dander-v020rc1
uv run python scripts/check_distribution.py /tmp/dander-v020rc1/*.whl /tmp/dander-v020rc1/*.tar.gz
```

## Checks

- Full suite: 610 passed; Ruff lint/format, strict mypy, and lock validation passed.
- Locked dependency audit found no known vulnerabilities.
- Terraform formatting and both repository roots validated with backends disabled.
- Wheel/sdist identity and archive inspection passed.
- Both artifacts installed outside the checkout, reported `0.2.0rc1`, generated valid source-free
  projects pinned to the candidate, and the generated Terraform root validated.

## Decisions

- Treat Salesforce as a `0.2.0` capability, preserving the `0.1.x` fixes-only policy.
- Keep candidate preparation version-only relative to merged `main`; `src/dander` is unchanged.
- Gate public candidate publication and retained-project GCP applies separately and explicitly.

## Remaining

- Open and merge the candidate PR through protected CI.
- Obtain explicit approval before tagging or publishing `0.2.0rc1`.
- Build the immutable source-free image from that exact public candidate.
- Pause existing schedules, review the additive Salesforce/upgrade plan, then obtain apply approval.
- Smoke-test Greenhouse, HubSpot, and Salesforce before restoring the first two schedules.

## Review First

- `CHANGELOG.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
