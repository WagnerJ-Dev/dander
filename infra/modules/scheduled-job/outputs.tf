output "artifact_repository" {
  description = "Artifact Registry repository resource name."
  value       = google_artifact_registry_repository.images.name
}

output "artifact_repository_id" {
  description = "Artifact Registry repository id."
  value       = google_artifact_registry_repository.images.repository_id
}

output "job_name" {
  description = "Cloud Run Job name."
  value       = google_cloud_run_v2_job.ingestion.name
}

output "runtime_service_account" {
  description = "Email of the least-privilege ingestion runtime identity."
  value       = google_service_account.runtime.email
}

output "runtime_service_account_name" {
  description = "Full resource name of the ingestion runtime identity."
  value       = google_service_account.runtime.name
}

output "scheduler_service_account_name" {
  description = "Full resource name of the scheduler identity."
  value       = google_service_account.scheduler.name
}

output "scheduler_job_name" {
  description = "Cloud Scheduler job name."
  value       = google_cloud_scheduler_job.ingestion.name
}
