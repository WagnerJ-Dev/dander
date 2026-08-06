# Morning Handoff

## Finished

- Added a read-only stage-zero permission preflight with conditional billing and WIF checks.
- Added source-free `image-publish` with bootstrap-account impersonation and immutable digests.
- Made admin and platform planning print review/apply commands; apply commands reuse saved plans.
- Made `init-platform-plan` render the complete manifest-defined hosted platform.
- Documented plan-first install/upgrade, least privilege, and immutable-image rollback.

## Try It

```bash
dander image-publish --project PROJECT --failure-alert-email OPERATOR_EMAIL
```

Run the printed platform-plan command, review its saved Terraform plan, then run the printed apply
command. `image-publish` intentionally requires a generated project without `src/`.

## Checks

- Focused bootstrap and CLI tests passed: `35 passed`.
- Full test suite passed: `763 passed`.
- Ruff formatting/lint and strict mypy passed.
- Main and stage-zero Terraform initialization/validation passed with backends disabled.
- Wheel/sdist inspection, external wheel install, project generation, and validation passed.

## Decisions

- Keep `dander init` as a compatibility shortcut; make plan-first commands the public path.
- Use predefined GCP roles, not a custom role; request billing/WIF permissions only on opt-in.
- Require source-free projects only for the new explicit image publication command.

## Remaining

- Protected CI and review must pass before this PR merges.
- Deep Salesforce endpoints and governed models remain separate sequential PRs.
- Candidate publication and live GCP acceptance still require explicit approval.

## Review First

- `src/dander/cli/main.py`
- `src/dander/bootstrap/permissions.py`
- `docs/getting-started.md`
