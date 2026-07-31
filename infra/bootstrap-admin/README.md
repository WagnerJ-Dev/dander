# Stage-zero administrative bootstrap

This root is the one-time precondition for the main `infra/` root. It creates only the remote GCS
state bucket, the empty `dander` Artifact Registry repository, the `dander-bootstrap` service
account, the project provisioning roles required by the main platform, and an explicit
token-creator binding for the approved administrator.

Its state is intentionally local and must be protected by the operator. After this apply, run the
main platform Terraform only with `bootstrap_service_account` set to the emitted service-account
email. The stage-zero caller remains outside the runtime and GitHub deploy identities.

For a project created by an older Dander revision, first export the existing platform state, import
the bucket/repository into this root, and remove only the old repository address from the main
state before applying the new configuration. Do not delete the remote repository during this
migration; the main root now reads it as a data source.
