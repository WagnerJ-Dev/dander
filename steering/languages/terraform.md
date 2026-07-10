# Terraform Conventions (HCL)

For the bootstrap CLI's infrastructure. Read alongside `01-security.md` (state & secrets rules).

## Toolchain & versions

- Pin Terraform and every provider version in `required_providers` / `required_version`.
- Format with `terraform fmt`; validate with `terraform validate`; lint with `tflint`.
- CI runs `fmt -check` → `validate` → `plan`. No manual `apply` outside the bootstrap flow.

## Structure

- **Module per concern**, provider-agnostic call site where possible:
  `modules/secret-manager`, `modules/iam`, `modules/compute-run`, `modules/bigquery`.
- GCP-first, but keep cloud-specific detail inside modules so an `aws/`/`azure/` sibling can be
  added later (mirrors the `SecretStoreProvider`/`ComputeProvider` abstraction in code).
- Standard files per module: `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`.
- Environments via separate var files / workspaces — never hardcoded project ids.

## Naming & style

- snake_case for resource names, variables, and outputs. Descriptive resource labels
  (`google_service_account.ingestion_runner`, not `sa1`).
- Every `variable` has a `type`, `description`, and a sensible `default` only when truly optional.
- Every `output` has a `description`. Tag/label resources with owner + module.

## Security (see 01-security.md)

- **Remote GCS backend** for state — never local state committed to the repo.
- **No secret values** in `.tf` or `.tfvars`. Reference Secret Manager resource names; commit only
  `*.tfvars.example`.
- Service accounts get **least-privilege** predefined roles; runtime identity via **Workload
  Identity Federation**, never long-lived keys.
- Mark sensitive variables/outputs `sensitive = true`.

## Documentation

- Module `README.md`: purpose, inputs, outputs, and an example call block.
- Comment non-obvious resource wiring and any intentional privilege grants (why this role).
- Keep the infra picture in sync with the module map in `00-project-overview.md`.
