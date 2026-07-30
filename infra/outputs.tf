output "dataset_ids" {
  description = "BigQuery dataset ids created by the bootstrap."
  value       = module.bigquery.dataset_ids
}

output "scheduled_job" {
  description = "Scheduled ingestion job details when enabled."
  value = var.enable_scheduled_job ? {
    job_name                = module.scheduled_job[0].job_name
    runtime_service_account = module.scheduled_job[0].runtime_service_account
    scheduler_job_name      = module.scheduled_job[0].scheduler_job_name
  } : null
}

output "secret_resources" {
  description = "Secret Manager resource names created by the bootstrap."
  value       = length(var.secret_ids) > 0 ? module.secret_manager[0].secret_resources : null
}

output "github_workload_identity" {
  description = "Keyless GitHub deployment identity details when enabled."
  value = var.github_repository != "" && var.enable_scheduled_job ? {
    provider_resource_name = module.github_wif[0].provider_resource_name
    service_account_email  = module.github_wif[0].service_account_email
  } : null
}
