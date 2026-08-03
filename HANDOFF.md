# Morning Handoff

## Finished

- Prepared `0.2.0rc2` from repaired protected `main` after the bounded rc1 Salesforce failure.
- Updated only release metadata, candidate assertions, release notes, and this handoff.
- Preserved the merged BigQuery JSON scalar fix without further runtime changes.
- Built and inspected the wheel/sdist, then installed and scaffolded from both outside the checkout.

## Try It

```bash
uv run dander --version
uv build --out-dir /tmp/dander-v020rc2
uv run python scripts/check_distribution.py /tmp/dander-v020rc2/*.whl /tmp/dander-v020rc2/*.tar.gz
```

## Checks

- Full suite: 611 passed; Ruff lint/format, strict mypy, and lock validation passed.
- Locked dependency audit found no known vulnerabilities.
- Terraform formatting and both repository roots validated with backends disabled.
- Wheel/sdist identity and archive inspection passed.
- Both artifacts installed outside the checkout, reported `0.2.0rc2`, generated valid source-free projects pinned to rc2, and the generated Terraform root validated.

## Decisions

- Keep candidate preparation version-only relative to repaired `main`; `src/dander` is unchanged.
- Keep all retained schedules paused until rc2 completes Greenhouse, HubSpot, and Salesforce proofs.
- Gate public publication and the retained-project image apply separately and explicitly.

## Remaining

- Merge the candidate PR through protected CI.
- Obtain explicit approval before tagging or publishing `0.2.0rc2`.
- Build and deploy the exact public source-free rc2 image.
- Rerun Greenhouse, HubSpot, and Salesforce, then replay Salesforce once.
- Restore Greenhouse and HubSpot schedules and require a final no-drift plan.

## Review First

- `CHANGELOG.md`
- `pyproject.toml`
- `.github/workflows/ci.yml`
