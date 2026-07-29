output "dataset_ids" {
  description = "BigQuery dataset ids created by the bootstrap."
  value       = module.bigquery.dataset_ids
}
