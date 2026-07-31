# GitHub Workload Identity Federation module

Creates a keyless GitHub OIDC provider constrained to one repository and exact branch or tag. The
principal can impersonate only a dedicated deployment service account. That account may push
Artifact Registry images, update Cloud Run, and act as only the explicitly supplied runtime
service accounts.
