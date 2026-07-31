# Stage-zero administrative bootstrap

This root is the one-time precondition for the main `infra/` root. It creates only the remote GCS
state bucket, the `dander` Artifact Registry repository, the `dander-bootstrap` service account,
the project provisioning roles required by the main platform, and explicit impersonation bindings
for approved operators and the proof workflow.

The stage-zero state is permanently stored in an existing GCS bucket. The current migration work is
code-only preparation: it does not migrate local state, mutate GCP, change GitHub settings, or
transfer state ownership. After a separately approved apply, the main platform Terraform must use
`bootstrap_service_account` set to the emitted service-account email. The stage-zero caller remains
outside the runtime and GitHub deploy identities.

## Permanent GCS backend

The administrative wrapper initializes this root with the following partial backend configuration:

```text
bucket = dander-sbx-harrison-20260729-tfstate
prefix = dander/bootstrap-admin/state
```

The bucket must already exist before stage-zero planning. GCS is the permanent stage-zero backend;
the existing platform state remains at
`gs://dander-sbx-harrison-20260729-tfstate/dander/state/default.tfstate`. The separate
`dander/bootstrap-admin/state` prefix prevents stage-zero state from sharing the platform-state
object.

Backend credentials are intentionally absent from Terraform configuration. Terraform uses the
operator's authenticated Google application-default credential context at initialization time.
Do not disable GCS locking, and do not migrate state until Object Versioning is verified on the
bucket. The backend design does not perform that migration automatically.

The wrapper requires `--operator-artifact-dir`, which must resolve outside the repository checkout.
It saves the plan as
`<operator-artifact-dir>/dander-admin-bootstrap.tfplan` and sets Terraform's `TF_DATA_DIR` to the
dedicated `<operator-artifact-dir>/terraform-data` subdirectory. Both operator directories are
created with mode `0700`, and the completed plan is restricted to mode `0600`. Terraform still runs
with `cwd=infra/bootstrap-admin`; an apply receives only the exact absolute path to that saved plan.

## Durable stage-zero state

Any provisional local stage-zero state and review artifacts must live in the operator-managed
directory outside this repository, normally:

`~/Library/Application Support/Dander/terraform/bootstrap-admin/<project>/`

Keep the directory at `0700`, state/backup/plan files at `0600`, and treat local state as migration
input and recovery material only. Never commit or upload it.
Do not reuse the obsolete `/tmp/dander-bootstrap-plan.p1DiGi/bootstrap.tfplan` or copy temporary
state from `/tmp`; recreate imports into a fresh stage-zero state file.

State, plans, backups, secrets, raw HubSpot responses, and `.terraform/` contents must never be
committed to or uploaded to GitHub. Locally generated evidence belongs under the ignored repository
`evidence/` path or in the secured operator directory, not in a commit or PR attachment.

## State retention and recovery

Before any separately approved state migration, make a timestamped, metadata-recorded backup of the
existing main platform state. Retain encrypted, access-controlled backups with the operator's
infrastructure records. The remote bucket must be Object Versioned, uses uniform access and
public-access prevention, and has `force_destroy = false`; keep its object generations as recovery
history and do not add routine lifecycle deletion.

## Separate state-ownership cutover

Importing the existing bucket and repository into fresh stage-zero state is a preparation step; it
does not transfer ownership from the main platform state. A later, separately approved cutover may
remove only the old resource addresses from the main state after a verified backup. That operation
is not part of the current plan-only task, must have explicit operator approval, and must be followed
by reviewed platform and stage-zero plans. It must never delete the actual Artifact Registry
repository or its cleanup policies. Do not apply either plan until that later review is complete.
