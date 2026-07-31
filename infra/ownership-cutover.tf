# Phase 3B prepares the stale platform-state binding for a later approved cutover.
# The physical repository is owned by stage zero and must be preserved.
removed {
  # The live state address is module.scheduled_job[0].google_artifact_registry_repository.images.
  # Terraform's removed.from syntax requires the counted module call without [0].
  from = module.scheduled_job.google_artifact_registry_repository.images

  lifecycle {
    destroy = false
  }
}
