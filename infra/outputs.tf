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
