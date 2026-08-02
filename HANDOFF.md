# Morning Handoff

## Finished

- Ran retained-project `0.1.0rc1` Greenhouse, HubSpot, replay, and overlap acceptance.
- Verified one overlapping HubSpot execution skipped and one succeeded without duplicate rows or
  lease/staging residue.
- Fixed the two acceptance defects: active runs now render in metadata history, and HubSpot's
  read-only full extraction cannot regress its committed watermark.
- Prepared `0.1.0rc2` as the required replacement candidate with public install pins updated.

## Try It

- Run `uv run dander --version` and `uv run pytest`.
- Install the built wheel or sdist outside the checkout, then run `dander new`, `dander validate`,
  and Terraform validation in the generated source-free project.

## Checks

- Ruff lint/format, strict mypy, dependency audit, and all 584 tests pass locally.
- Root, stage-zero, and generated-project Terraform init/validate pass.
- Fresh `0.1.0rc2` wheel and sdist pass archive checks, install outside the checkout, and generate
  valid source-free projects.

## Decisions

- `0.1.0rc1` cannot be promoted because retained acceptance exposed packaged runtime defects.
- Monotonic retention is narrow to deliberate read-only/full-refresh cursor paths; normal filtered
  extraction retains its existing compare-and-set behavior.

## Remaining

- Merge the protected-main candidate-fix PR and publish `0.1.0rc2` through trusted publishing.
- Deploy the source-free `rc2` image and rerun the exposing scenarios plus the bounded smoke suite.
- Complete the fresh-project source-free Greenhouse rehearsal, then publish and smoke `0.1.0`.

## Review First

- `src/dander/runtime.py`
- `src/dander/state/run_history.py`
- `tests/test_runtime.py`
