# Roll back a hosted Dander release

Rollback restores a previously successful project configuration and immutable runtime image. It
does not undo changes made in a source system, remove ingested rows, or destructively reverse a
BigQuery schema.

## Identify the known-good deployment

Record the last project commit that completed a hosted run and its exact Artifact Registry
`@sha256:` image digest. Create a new rollback branch and commit that restores the compatible
package/plugin pins and manifest configuration; do not rewrite shared Git history.

## Pause and restore through reviewed plans

1. Set every affected pipeline's tracked `paused` value to `true`.
2. Run `dander init-platform-plan` with the known-good image digest and the installation's existing
   state bucket, bootstrap service account, alert address, and guarded-runtime inputs.
3. Reject any plan that changes datasets, state, secret values, unrelated jobs, or runtime IAM.
4. Review the saved plan with `terraform -chdir=infra show -no-color dander-bootstrap.tfplan`.
5. Run `dander init-platform-apply`; it applies only that saved plan.
6. Execute each paused job manually. Verify run history, transforms/tests, row counts, cursors,
   leases, and staging cleanup.
7. Restore the tracked schedule state through a second reviewed plan and apply.
8. Repeat `init-platform-plan` and require Terraform to report `No changes.`

If the prior image is incompatible with the current manifest or deployed schema, stop and repair
forward. Never manually edit Terraform state, `_dander_leases`, `_dander_watermarks`, or staging
tables to manufacture a rollback.
