# Morning Handoff

## Finished

- Completed retained-project `0.1.0rc2` Greenhouse, HubSpot, replay, overlap, cleanup, scheduler,
  alert, and no-drift acceptance.
- Confirmed public `rc2` installation and source-free project generation outside the checkout.
- Reproduced a fresh-project first-run IAM propagation race during independent installation.
- Added a bounded impersonation-readiness wait and prepared replacement candidate `0.1.0rc3`.

## Try It

- Run `uv run dander --version` and `uv run pytest`.
- Install the built wheel or sdist outside the checkout, then run `dander new`, `dander validate`,
  and Terraform validation in the generated source-free project.

## Checks

- Ruff lint/format, strict mypy, dependency audit, and all 584 tests pass locally.
- Root, stage-zero, and generated-project Terraform init/validate pass.
- Ruff lint/format, strict mypy, dependency audit, and all 586 tests pass locally.
- Root, stage-zero, and generated-project Terraform init/validate pass.
- Fresh `0.1.0rc3` wheel and sdist pass archive checks, install outside the checkout, and generate
  a valid source-free project.

## Decisions

- The clean-room failure is a packaged bootstrap defect, so `rc2` cannot be promoted.
- Readiness probes the permission Dander actually needs and stops after a bounded 60-second wait.

## Remaining

- Complete the full local and protected-main checks for `rc3`, then publish it through trusted
  publishing.
- Resume the fresh-project installation and rerun the bounded retained-project smoke suite.
- Publish and smoke final `0.1.0` after the replacement candidate passes.

## Review First

- `src/dander/bootstrap/project.py`
- `src/dander/cli/main.py`
- `tests/bootstrap/test_project_bootstrap.py`
