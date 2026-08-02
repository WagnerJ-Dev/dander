# Morning Handoff

## Finished

- Completed retained-project `0.1.0rc2` Greenhouse, HubSpot, replay, overlap, cleanup, scheduler,
  alert, and no-drift acceptance.
- Published `0.1.0rc4`; its bounded IAM-propagation gate recovered the fresh-project cost guard.
- Completed the public-package, source-free clean-room Greenhouse installation: 21 rows, one model,
  three tests, one catalog asset, enabled schedule, and clean Terraform plan.
- Prepared `0.1.0rc5` to replace a plan-only `dander init` traceback with a normal usage error.

## Try It

- Run `uv run dander --version` and `uv run pytest`.
- Install the built wheel or sdist outside the checkout, then run `dander new`, `dander validate`,
  and Terraform validation in the generated source-free project.

## Checks

- Ruff lint/format, strict mypy, dependency audit, and all 588 tests pass locally.
- Root, stage-zero, and generated-project Terraform init/validate pass.
- Fresh `0.1.0rc4` wheel and sdist pass archive checks, install outside the checkout, and generate
  a valid source-free project.
- Fresh-project hosted Greenhouse execution and final Terraform no-drift plan pass on public rc4.
- Fresh `0.1.0rc5` wheel and sdist pass archive checks, external installation, source-free project
  generation, and generated Terraform validation.

## Decisions

- The documented clean-room path passes on rc4; the surfaced plan-only traceback is still a narrow
  user-facing CLI defect and receives one final candidate fix.
- Candidate acceptance remains source-free and package-backed; repository source is not copied into
  either proof project.

## Remaining

- Validate, merge, and publish `0.1.0rc5` through the protected paths.
- Run retained Greenhouse/HubSpot acceptance and final no-drift verification on rc5.
- Publish and smoke final `0.1.0` when the replacement candidate passes.

## Review First

- `src/dander/cli/main.py`
- `tests/cli/test_init_cli.py`
- `CHANGELOG.md`
