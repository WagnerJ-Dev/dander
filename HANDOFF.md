# Morning Handoff

## Finished

- Containerized Dander with pinned dependencies and a non-root runtime.
- Provisioned an Artifact Registry repository, two dedicated identities, and a Cloud Run Job.
- Enabled the daily 09:00 America/New_York Scheduler job after a manual execution passed.
- Proved Scheduler OAuth invocation and the guarded BigQuery SCD1 path with 21 distinct jobs.
- Left the live `$5` billing guard active; Terraform remote state has no drift.

## Try It

```bash
gcloud run jobs execute dander-greenhouse-public \
  --project=dander-sbx-harrison-20260729 --region=us-central1 --wait
```

The daily schedule is `0 9 * * *` in `America/New_York`. Use
`gcloud scheduler jobs pause dander-greenhouse-public-daily --location=us-central1` to stop it.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 322 passed.
- `terraform fmt -check -recursive`, `terraform validate`, and final no-change plan — passed.
- Container build/smoke, direct execution, and Scheduler execution — passed; table has 21 unique rows.

## Decisions

- Deploy by immutable image digest and retain only three recent images.
- Keep runtime writes scoped to `raw`; use a separate invoker-only Scheduler identity.
- Apply paused first, prove a manual run, then enable the daily schedule.

## Remaining

- Add Harvest v3 credentials only if Greenhouse account access becomes available.
- Review or remove default project service accounts with broad Editor grants.
- Stream/chunk large endpoints and add controlled target-schema evolution.
- Monitor the first automatic 09:00 run and billing export before expanding frequency or scope.

## Review First

- `infra/modules/scheduled-job/main.tf`
- `Dockerfile`
- `README.md`
