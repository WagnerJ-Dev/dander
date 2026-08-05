# Morning Handoff

## Finished

- Prepared Dander `0.5.1` as a narrow catalog-correction patch.
- Updated Salesforce and ServiceNow recommendations to their published `0.2.0` releases.
- Corrected both compatibility ranges to Dander `>=0.5.0,<0.6`.
- Updated release identity, distribution assertions, tests, and release notes.

## Try It

```bash
uv run dander plugins search
```

## Checks

- Focused catalog, CLI, distribution, scaffold, and graph-deployment tests passed.
- Ruff, formatting, strict mypy, dependency audit, and all 747 tests passed.
- Platform and stage-zero Terraform formatting and validation passed.
- Wheel and source distribution inspection, source-free installation, generated project validation,
  generated Terraform validation, container build, and runtime contract checks passed.

## Decisions

- Keep this patch limited to published catalog metadata and the required `0.5.1` release identity.
- Require Dander `0.5.x` because both recommended connector `0.2.0` packages use the API introduced
  in that line.

## Remaining

- Merge the focused pull request through protected CI.
- Tag and publish `0.5.1` through trusted publishing.
- Verify the exact public installation and catalog output.

## Review First

- `src/dander/plugins/catalog.py`
- `tests/plugins/test_catalog.py`
- `CHANGELOG.md`
