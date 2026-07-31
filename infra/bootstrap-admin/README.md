# Stage-zero administrative bootstrap

This root is the one-time precondition for the main `infra/` root. It creates only the remote GCS
state bucket, the `dander-bootstrap` service account, the project provisioning roles required by
the main platform, and an explicit token-creator binding for the approved administrator.

Its state is intentionally local and must be protected by the operator. After this apply, run the
main platform Terraform only with `bootstrap_service_account` set to the emitted service-account
email. The stage-zero caller remains outside the runtime and GitHub deploy identities.
