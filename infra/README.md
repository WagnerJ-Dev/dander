# infra/ — Terraform for the dander bootstrap CLI

`dander init` runs these modules to stand up the GCP data platform. GCP-first; a cloud-specific
detail stays inside each module so `aws/`/`azure/` siblings can be added later without changing the
call sites (mirrors the `SecretStoreProvider` / `ComputeProvider` abstractions in code).

## Modules

| Module | Provisions |
|---|---|
| `modules/bigquery` | `raw` / `staging` / `marts` datasets. **Implemented.** |
| `modules/scheduled-job` | Artifact Registry, least-privilege identities, public-ingestion Cloud Run Job, and daily Scheduler job. **Implemented.** |
| `modules/secret-manager` | Named secret containers and per-secret runtime access; never secret values. **Implemented.** |
| `modules/github-wif` | Repository/ref-scoped GitHub OIDC and a keyless deployment identity. **Implemented.** |
| `modules/cost-guard` | Project budget, Pub/Sub, and simulation-first Gen 2 billing kill switch. **Implemented.** |

The root module always calls `modules/bigquery` and can opt into the remaining modules.
`dander init` configures the required GCS backend, creates a saved plan, and applies that exact
plan only after the caller supplies `--apply` and confirms interactively. The state bucket must
already exist:

```bash
uv run dander init --project my-gcp-project --state-bucket my-existing-tfstate-bucket
```

To plan the complete hosted runtime, first push an image and resolve its immutable digest:

```bash
uv run dander init \
  --project my-gcp-project \
  --state-bucket my-existing-tfstate-bucket \
  --enable-runtime \
  --billing-account ABCDEF-123456-ABCDEF \
  --container-image us-central1-docker.pkg.dev/my-gcp-project/dander/dander@sha256:DIGEST \
  --secret-id greenhouse-client-secret \
  --github-repository owner/repository \
  --enable-cost-guard
```

This still plans by default. Add `--apply` only after reviewing the saved plan. Secret values must
be added separately with `gcloud secrets versions add`; Terraform intentionally never receives
them. GitHub WIF grants Artifact Registry access only on the Dander repository, Cloud Run developer
access, and `actAs` only on Dander's runtime identities.

The cost guard is simulation-only by default. `--live-cost-guard` allows its over-budget handler
to unlink billing and therefore appears by name in the apply confirmation. That action can stop
services and delete resources, while delayed billing reports can still exceed the configured
amount. Deploying the Gen 2 function uses billable Cloud Build, Cloud Run, Storage, and Artifact
Registry components; a plan never asserts that the result will cost exactly zero.

For the scheduled slice, copy `sandbox.auto.tfvars.example` to ignored
`sandbox.auto.tfvars`, supply an immutable Artifact Registry digest, and leave
`scheduler_paused = true` for the first apply. Run the Cloud Run Job manually, verify its guarded
write, selected transform tests, and registry compilation, then change only that value to `false`
and apply a reviewed saved plan. The runtime identity can create BigQuery jobs, edit `raw`,
`staging`, and `marts`, inspect Pub/Sub guard wiring, and read billing budget metadata. Optional
Dataplex publication is disabled by default and adds catalog IAM only when enabled. The scheduler
identity can invoke only the named Cloud Run Job.

## Rules (see `steering/01-security.md` and `steering/languages/terraform.md`)

- **Remote GCS backend** for state — never local state committed to the repo.
- **No secret values** in `.tf`/`.tfvars`; reference Secret Manager. Commit only `*.tfvars.example`.
- Project id / region are always parameterized, never hard-coded.
- Normal bootstrap applies run through the CLI. A reviewed, saved Terraform plan is also the
  operational path for the optional scheduled-job slice.
