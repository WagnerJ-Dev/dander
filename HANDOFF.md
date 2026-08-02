# Morning Handoff

## Finished

- Published and deployed source-free `0.1.0rc6` with both retained schedules paused.
- Reproduced the rc6 failure: BigQuery serializes concurrent DML by table, so separate pipeline
  rows in one lease table still caused cross-pipeline aborts and a misleading task retry success.
- Prepared `0.1.0rc7` with deterministic per-pipeline lease tables and bounded retry support for
  both observed BigQuery serialization errors.
- Added regression coverage for pipeline isolation, stable table naming, and alternate-error retry.
- Preserved the completed fresh-project source-free Greenhouse proof from public rc4.

## Try It

- Run `uv run pytest` and `uv run dander --version`.
- Build with `uv build`, install the wheel outside the checkout, then run `dander new`,
  `dander validate`, and `terraform -chdir=infra validate`.

## Checks

- All 594 tests, Ruff lint/format, strict mypy, dependency audit, and lock validation pass.
- Root, stage-zero, and generated-project Terraform formatting and validation pass.

## Decisions

- Isolate lease DML by pipeline because BigQuery contention is table-wide, not row-scoped.
- Leave the historical shared lease table untouched; rc7 creates deterministic isolated tables on
  demand and retains exact-error retry for same-pipeline races.
- Keep both retained schedulers paused until rc7 acceptance finishes.

## Remaining

- Build and externally install rc7, then merge and publish it through protected environments.
- Deploy the public source-free rc7 image and rerun the exact cross-pipeline overlap first.
- Complete retained acceptance, restore schedules, and require a no-drift Terraform plan.
- Publish and smoke final `0.1.0` when rc7 passes.

## Review First

- `src/dander/_bigquery_retry.py`
- `src/dander/state/lease.py`
- `tests/state/test_lease.py`
