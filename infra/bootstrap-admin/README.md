# Stage-zero administrative bootstrap

This root is the one-time precondition for the main `infra/` root. It creates only the remote GCS
state bucket, the empty `dander` Artifact Registry repository, the `dander-bootstrap` service
account, the project provisioning roles required by the main platform, and an explicit
token-creator binding for the approved administrator.

Its state is intentionally local and must be protected by the operator. After this apply, run the
main platform Terraform only with `bootstrap_service_account` set to the emitted service-account
email. The stage-zero caller remains outside the runtime and GitHub deploy identities.

## State retention and recovery

Stage zero creates the remote bucket that will hold the main platform's Terraform state, so the
`infra/bootstrap-admin` root intentionally uses operator-managed local state for its own one-time
bootstrap record. Keep that state out of the repository and retain encrypted, access-controlled
backups with the operator's infrastructure records. The remote bucket created for the main root is
versioned, uses uniform access and public-access prevention, and has `force_destroy = false`; keep
its object generations as the recovery history and do not add routine lifecycle deletion. If a
project was created by an older revision, import the existing bucket and repository into this root
and preserve the existing state objects rather than recreating or deleting them.

For a project created by an older Dander revision, first export the existing platform state, import
the bucket/repository into this root, and remove only the old repository address from the main
state before applying the new configuration. Do not delete the remote repository during this
migration; the main root now reads it as a data source.
