# Stage-zero administrative bootstrap

This root is the one-time precondition for the main `infra/` root. It creates only the remote GCS
state bucket, the `dander` Artifact Registry repository, the `dander-bootstrap` service account,
the project provisioning roles required by the main platform, and explicit impersonation bindings
for approved operators and the proof workflow.

The current migration work is plan-only preparation. It does not apply this root, mutate GCP, change
GitHub settings, or transfer state ownership. After a separately approved apply, the main platform
Terraform must use `bootstrap_service_account` set to the emitted service-account email. The
stage-zero caller remains outside the runtime and GitHub deploy identities.

## Durable stage-zero state

Stage-zero state and review artifacts must live in the operator-managed directory outside this
repository, normally:

`~/Library/Application Support/Dander/terraform/bootstrap-admin/<project>/`

Keep the directory at `0700`, state/backup/plan files at `0600`, and never commit or upload them.
Do not reuse the obsolete `/tmp/dander-bootstrap-plan.p1DiGi/bootstrap.tfplan` or copy temporary
state from `/tmp`; recreate imports into a fresh stage-zero state file.

## State retention and recovery

Stage zero creates the remote bucket that holds the main platform's Terraform state, so this root
uses operator-managed local state for its own one-time bootstrap record. Before recreating imports,
make a timestamped, metadata-recorded backup of the existing main platform state. Retain encrypted,
access-controlled backups with the operator's infrastructure records. The remote bucket is
versioned, uses uniform access and public-access prevention, and has `force_destroy = false`; keep
its object generations as recovery history and do not add routine lifecycle deletion.

## Separate state-ownership cutover

Importing the existing bucket and repository into fresh stage-zero state is a preparation step; it
does not transfer ownership from the main platform state. A later, separately approved cutover may
remove only the old resource addresses from the main state after a verified backup. That operation
is not part of the current plan-only task, must have explicit operator approval, and must be followed
by reviewed platform and stage-zero plans. It must never delete the actual Artifact Registry
repository or its cleanup policies. Do not apply either plan until that later review is complete.
