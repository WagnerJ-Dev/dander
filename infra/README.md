# infra/ — Terraform for the dander bootstrap CLI

`dander init` runs these modules to stand up the GCP data platform. GCP-first; a cloud-specific
detail stays inside each module so `aws/`/`azure/` siblings can be added later without changing the
call sites (mirrors the `SecretStoreProvider` / `ComputeProvider` abstractions in code).

## Modules (planned)

| Module | Provisions |
|---|---|
| `modules/bigquery` | `raw` / `staging` / `marts` datasets. **(scaffolded)** |
| `modules/secret-manager` | Secret entries + access bindings. |
| `modules/iam` | Least-privilege service accounts + Workload Identity Federation (no long-lived keys). |
| `modules/compute-run` | Cloud Run jobs that run connectors. |

## Rules (see `steering/01-security.md` and `steering/languages/terraform.md`)

- **Remote GCS backend** for state — never local state committed to the repo.
- **No secret values** in `.tf`/`.tfvars`; reference Secret Manager. Commit only `*.tfvars.example`.
- Project id / region are always parameterized, never hard-coded.
- The CLI runs `apply`; humans and agents do not (agents are limited to `fmt`/`validate`/`plan`).
