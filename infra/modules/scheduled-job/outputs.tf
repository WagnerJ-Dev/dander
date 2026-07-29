output "artifact_repository" {
  description = "Artifact Registry repository resource name."
  value       = google_artifact_registry_repository.images.name
}

output "job_name" {
  description = "Cloud Run Job name."
  value       = google_cloud_run_v2_job.ingestion.name
}

output "runtime_service_account" {
  description = "Email of the least-privilege ingestion runtime identity."
  value       = google_service_account.runtime.email
}

output "scheduler_job_name" {
  description = "Cloud Scheduler job name."
  value       = google_cloud_scheduler_job.ingestion.name
}
