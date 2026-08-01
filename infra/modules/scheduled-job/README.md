# Additive scheduled pipelines

This module turns the expanded `dander.yaml` pipeline map into independent Cloud Run Jobs and
Cloud Scheduler triggers. Pipelines share the immutable container image and BigQuery datasets, but
each receives separate runtime and scheduler service accounts. Secret bindings are supplied to the
root Secret Manager module so a runtime can access only the credentials named by its pipeline.

The original singleton Greenhouse resources move in state to the `greenhouse_jobs` key. This keeps
the live job, scheduler, identities, and IAM bindings intact while new pipelines are added with
`for_each`.

```hcl
pipelines = {
  greenhouse_jobs = {
    job_name                     = "dander-greenhouse-public"
    runtime_service_account_id   = "dander-runtime"
    scheduler_service_account_id = "dander-scheduler"
    source                       = "greenhouse_job_board"
    models                       = ["stg_greenhouse__jobs"]
    build_models                 = true
    publish_dataplex             = false
    schedule                     = "0 9 * * *"
    time_zone                    = "America/New_York"
    paused                       = false
    secret_env                   = {}
  }
}
```

Every hosted job executes `dander run <pipeline> --config /app/dander.yaml`, so local and cloud
execution resolve the same connector, model selection, and metadata policy. New schedules remain
paused until their manual proof succeeds.
