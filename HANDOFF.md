# Morning Handoff

## Finished

- Completed retained-project `0.1.0rc2` Greenhouse, HubSpot, replay, overlap, cleanup, scheduler,
  alert, and no-drift acceptance.
- Published `0.1.0rc3`, confirmed its public source-free installation, and resumed the clean-room
  project beyond the original bootstrap impersonation failure.
- Reproduced a second first-run race while Cloud Functions resolved the new cost-guard builder.
- Added an explicit Terraform propagation gate and prepared replacement candidate `0.1.0rc4`.

## Try It

- Run `uv run dander --version` and `uv run pytest`.
- Install the built wheel or sdist outside the checkout, then run `dander new`, `dander validate`,
  and Terraform validation in the generated source-free project.

## Checks

- Ruff lint/format, strict mypy, dependency audit, and all 584 tests pass locally.
- Root, stage-zero, and generated-project Terraform init/validate pass.
- Ruff lint/format, strict mypy, dependency audit, and all 587 tests pass locally.
- Root, stage-zero, and generated-project Terraform init/validate pass.
- Fresh `0.1.0rc4` wheel and sdist pass archive checks, install outside the checkout, and generate
  a valid source-free project.

## Decisions

- The clean-room Cloud Functions failure is a packaged provisioning defect, so `rc3` cannot be
  promoted.
- The one-time 120-second gate follows Google's documented propagation boundary and is scoped only
  to initial cost-guard function creation.

## Remaining

- Complete the full local and protected-main checks for `rc4`, then publish it through trusted
  publishing.
- Resume the fresh-project installation and rerun the bounded retained-project smoke suite.
- Publish and smoke final `0.1.0` after the replacement candidate passes.

## Review First

- `infra/modules/cost-guard/main.tf`
- `infra/modules/cost-guard/versions.tf`
- `tests/infra/test_clean_bootstrap_contract.py`
