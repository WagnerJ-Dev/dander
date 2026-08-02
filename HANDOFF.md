# Morning Handoff

## Finished

- Published `0.1.0rc5` and deployed its source-free image with both retained schedules paused.
- Reproduced the retained overlap failure: different pipelines concurrently touching the shared
  BigQuery lease table could abort fenced finalization transactions.
- Prepared `0.1.0rc6` with bounded, exact-error retries around BigQuery control mutations and
  transactionally fenced finalizers.
- Added regression coverage proving retry, unrelated-error pass-through, exhaustion, and the
  hosted SCD1 finalizer path.
- Preserved the completed fresh-project source-free Greenhouse proof from public rc4.

## Try It

- Run `uv run pytest` and `uv run dander --version`.
- Build with `uv build`, install the wheel outside the checkout, then run `dander new`,
  `dander validate`, and `terraform -chdir=infra validate`.

## Checks

- All 592 tests, Ruff lint/format, strict mypy, dependency audit, and lock validation pass.
- Root, stage-zero, and generated-project Terraform formatting and validation pass.
- Fresh rc6 wheel and sdist pass archive checks; the wheel installs outside the checkout and
  generates a validated source-free project with the rc6 Docker pin and no `src/` directory.

## Decisions

- Retry only the exact BigQuery concurrent-update transaction abort; fencing, stale-cursor,
  permission, schema, and unrelated BigQuery errors still fail immediately.
- Retry the entire aborted transaction at most five submissions, preserving atomic publication and
  cursor semantics.
- Keep both retained schedulers paused until rc6 acceptance finishes.

## Remaining

- Merge and publish `0.1.0rc6` through protected GitHub and PyPI environments.
- Deploy the public source-free rc6 image and rerun the exact cross-pipeline overlap first.
- Complete retained acceptance, restore schedules, and require a no-drift Terraform plan.
- Publish and smoke final `0.1.0` when rc6 passes.

## Review First

- `src/dander/_bigquery_retry.py`
- `src/dander/state/lease.py`
- `src/dander/writer/bigquery.py`
