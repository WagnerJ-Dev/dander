# infra/ — Terraform for the dander bootstrap CLI

`dander init` runs these modules to stand up the GCP data platform. GCP-first; a cloud-specific
detail stays inside each module so `aws/`/`azure/` siblings can be added later without changing the
call sites (mirrors the `SecretStoreProvider` / `ComputeProvider` abstractions in code).

## Modules

| Module | Provisions |
|---|---|
| `modules/bigquery` | `raw` / `staging` / `marts` datasets. **Implemented.** |
| `modules/scheduled-job` | Artifact Registry, least-privilege identities, public-ingestion Cloud Run Job, and daily Scheduler job. **Implemented.** |
| `functions/stop_billing` | Pub/Sub-triggered, simulation-testable billing kill switch. |
| `modules/secret-manager` | Secret entries + access bindings. |
| `modules/iam` | Least-privilege service accounts + Workload Identity Federation (no long-lived keys). |
| `modules/compute-run` | Cloud Run jobs that run connectors. |

The root module always calls `modules/bigquery` and can opt into `modules/scheduled-job`.
`dander init` configures the required GCS backend, creates a saved plan, and applies that exact
plan only after the caller supplies `--apply` and confirms interactively. The state bucket must
already exist:

```bash
uv run dander init --project my-gcp-project --state-bucket my-existing-tfstate-bucket
```

For the scheduled slice, copy `sandbox.auto.tfvars.example` to ignored
`sandbox.auto.tfvars`, supply an immutable Artifact Registry digest, and leave
`scheduler_paused = true` for the first apply. Run the Cloud Run Job manually, verify the guarded
write, then change only that value to `false` and apply a reviewed saved plan. The runtime identity
can create BigQuery jobs, edit only the `raw` dataset, inspect Pub/Sub guard wiring, and read billing
budget metadata. The scheduler identity can invoke only the named Cloud Run Job.

## Rules (see `steering/01-security.md` and `steering/languages/terraform.md`)

- **Remote GCS backend** for state — never local state committed to the repo.
- **No secret values** in `.tf`/`.tfvars`; reference Secret Manager. Commit only `*.tfvars.example`.
- Project id / region are always parameterized, never hard-coded.
- Normal bootstrap applies run through the CLI. A reviewed, saved Terraform plan is also the
  operational path for the optional scheduled-job slice.
