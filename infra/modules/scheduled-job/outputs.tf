output "artifact_repository" {
  description = "Artifact Registry repository resource name."
  value       = data.google_artifact_registry_repository.images.name
}

output "artifact_repository_id" {
  description = "Artifact Registry repository id."
  value       = data.google_artifact_registry_repository.images.repository_id
}

output "jobs" {
  description = "Hosted pipeline resource details keyed by pipeline id."
  value = {
    for id, pipeline in var.pipelines : id => {
      job_name                       = google_cloud_run_v2_job.ingestion[id].name
      runtime_service_account        = google_service_account.runtime[id].email
      runtime_service_account_name   = google_service_account.runtime[id].name
      scheduler_job_name             = google_cloud_scheduler_job.ingestion[id].name
      scheduler_service_account      = google_service_account.scheduler[id].email
      scheduler_service_account_name = google_service_account.scheduler[id].name
    }
  }
}

output "runtime_service_accounts" {
  description = "Runtime service-account emails keyed by pipeline id."
  value       = { for id, account in google_service_account.runtime : id => account.email }
}

output "runtime_service_account_names" {
  description = "Runtime service-account resource names keyed by pipeline id."
  value       = { for id, account in google_service_account.runtime : id => account.name }
}

output "scheduler_service_account_names" {
  description = "Scheduler service-account resource names keyed by pipeline id."
  value       = { for id, account in google_service_account.scheduler : id => account.name }
}
