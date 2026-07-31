# Scheduled public pipeline

Packages the credential-free Greenhouse Job Board path as a daily Cloud Run Job. Each run ingests
public jobs, builds and tests only `stg_greenhouse__jobs`, then compiles a local semantic registry.
Stage zero creates the shared Artifact Registry repository before this module is applied. The
module then uses that repository, plus distinct runtime and scheduler service accounts,
least-privilege IAM, the job, and an OAuth-authenticated Cloud Scheduler trigger.

The schedule is paused by default. Apply it in that state, execute the Cloud Run Job manually, and
enable the schedule only after the guarded BigQuery write succeeds. `container_image` must use an
immutable `@sha256:` digest.

```hcl
module "scheduled_job" {
  source = "./modules/scheduled-job"

  project_id         = "my-project"
  region             = "us-central1"
  billing_account_id = "000000-000000-000000"
  container_image    = "us-central1-docker.pkg.dev/my-project/dander/dander@sha256:..."
  scheduler_paused   = true
  publish_dataplex   = false
  runtime_build_models = true
}
```

Outputs expose the repository name, Cloud Run Job name, runtime identity, and Scheduler job name.
The module stores no source-system credentials because this connector reads public jobs only.
Dataplex publication is disabled by default because stored aspects may be billable; enabling it
also enables the API and grants the runtime catalog-editor access.
