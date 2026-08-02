# Morning Handoff

## Finished

- Published `dander-platform==0.1.0rc1` from the exact green main commit through trusted publishing.
- Added the alpha warning, release notes, hosted Greenhouse quickstart, upgrade guide, security
  policy, supported-version statement, and one known-limitations page.
- Corrected the retained-project record: both schedules are enabled, while the jobs still use the
  pre-candidate source-built image.
- Kept the `0.1.x` contract fixes-only; new capabilities remain reserved for `0.2.0`.

## Try It

- Follow `docs/getting-started.md` from a machine with the documented GCP prerequisites.
- Run `uv tool install --force dander-platform==0.1.0rc1` and `dander --version`.

## Checks

- Ruff lint/format, strict mypy, dependency audit, and all 581 tests pass locally.
- Root and stage-zero Terraform format/init/validate pass; tracked Greenhouse and HubSpot dry-runs
  pass.
- Fresh wheel and sdist builds pass archive checks; both install outside the checkout and generate
  source-free projects whose CLI and Terraform configuration validate.

## Decisions

- Only the latest patch of the current `0.x` minor is supported.
- The public hosted starter makes no elapsed-time promise and starts with a paused Greenhouse job.
- GitHub private vulnerability reporting is the security channel; no public security email is used.

## Remaining

- Merge the alpha-furniture PR, then enable private vulnerability reporting.
- Obtain separate approval before pausing schedules or applying the source-free rc1 candidate.
- Complete one independent source-free Greenhouse installation before final publication; the
  30-day operator soak starts only after `0.1.0` ships.

## Review First

- `docs/getting-started.md`
- `docs/upgrading.md`
- `SECURITY.md`
