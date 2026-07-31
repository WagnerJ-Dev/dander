# Bootstrap identity

This module creates the separate `dander-bootstrap` service account used for approved Terraform
bootstrap runs. Its project roles are intentionally broader than the runtime identity because it
creates IAM, APIs, data services, and compute resources. It must not be attached to Cloud Run or
Cloud Scheduler, and GitHub WIF never grants access to it.

Use impersonation for the short bootstrap window, then run the workload with the dedicated runtime
identity. The optional billing-account binding is created only when a billing account is supplied;
it is required for Terraform-managed budget resources and should be removed when the bootstrap is
complete if the organization's operating model permits.
