# Phase 3B ownership preparation

This change prepares one stale platform-state ownership binding for a later, separately approved
cutover. It does not remove a live state binding, change a resource, or run a Terraform plan.

## Corrected discovery

The live platform state at generation `1785368475607577` contains the stale managed address:

```text
module.scheduled_job[0].google_artifact_registry_repository.images
```

Its stored identity is:

```text
projects/dander-sbx-harrison-20260729/locations/us-central1/repositories/dander
```

The identity matches the real Docker repository in project `dander-sbx-harrison-20260729`,
location `us-central1`, repository ID `dander`. The same repository is managed in stage-zero as:

```text
google_artifact_registry_repository.images
```

The stage-zero state remains at generation `1785527056966752`.

The live platform state contains no platform-state bucket resource. In particular, no platform
binding exists for `google_storage_bucket.terraform_state`. The `infra/bootstrap-admin` root
exclusively manages that bucket; the platform root only consumes the existing bucket through its
GCS backend configuration. No bucket `removed` block is therefore selected or invented.

The repository binding is stale because the pre-refactor scheduled-job module managed the
repository, while the current module reads it as a data source. The stage-zero root was introduced
as the owner of the repository and state bucket. This PR contains no broad module removal, no
unrelated resource selection, and no cost-guard resource is selected.

Terraform's `removed.from` syntax does not accept a counted module instance in this position. The
configuration therefore uses `module.scheduled_job.google_artifact_registry_repository.images`,
the valid module-call form. The current platform configuration has exactly one scheduled-job
instance (`count = var.enable_scheduled_job ? 1 : 0`), so this covers the verified live `[0]`
address and does not broaden the selected resource.

## Prepared binding

```hcl
removed {
  from = module.scheduled_job.google_artifact_registry_repository.images

  lifecycle {
    destroy = false
  }
}
```

The `destroy = false` lifecycle preserves the real repository when this binding is later applied
through the separately approved ownership-cutover procedure.
