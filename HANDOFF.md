# Morning Handoff

## Finished

- Replaced the stale hosted runtime with the Linux/AMD64 image built from commit `554669d` and pinned Cloud Run to manifest digest `sha256:765b5a9b8fd5a2db7514238809a5565e4779e8a2e200b4c9d58c28c44abc2a69`.
- Applied the reviewed Terraform plan as one in-place Cloud Run image update: 0 added, 1 changed, 0 destroyed.
- Completed execution `dander-greenhouse-public-wngdn` successfully with ingestion, selected transform build/tests, and local catalog compilation.
- Verified 25 raw rows, 25 staging rows, 25 distinct job ids, and zero null job ids or titles.
- Left the daily scheduler enabled for 09:00 America/New_York with no IAM, dataset, billing, scheduler, or Terraform source changes.

## Try It

- Inspect the latest run with `gcloud run jobs executions describe dander-greenhouse-public-wngdn --region=us-central1`.
- Query `raw.greenhouse_job_board_jobs` and `staging.stg_greenhouse__jobs` directly; `INFORMATION_SCHEMA` access is not required.

## Checks

- Exact production command parsed successfully in the replacement container, and both selected model files were present.
- Targeted CLI, bootstrap, and transform tests passed: 54 passed.
- Manual Cloud Run execution succeeded in one task attempt with container exit code 0.
- Direct BigQuery assertions passed: raw/staging counts matched at 25, ids were unique and non-null, and titles were non-null.
- Final Terraform 1.15.8 plan returned exit code 0 with no changes.

## Decisions

- Recovered through the existing Terraform-managed immutable-image path rather than introducing `gcloud` drift.
- Kept Dataplex publication disabled and retained local ephemeral catalog output.
- Kept the scheduler enabled because the manual end-to-end proof passed before its next invocation.

## Remaining

- Observe the next scheduled execution after 09:00 America/New_York; no recovery blocker remains.
- Optional `INFORMATION_SCHEMA` metadata access remains unavailable, but direct table metadata and row queries work.

## Review First

- Cloud Run execution `dander-greenhouse-public-wngdn`
- Terraform plan SHA-256 `66c08b2e3517fbd14b7239bac2455d6eaaf7db1f35a4dc1ba8be3dfe980c3f53`
- `infra/sandbox.auto.tfvars` immutable runtime image reference
