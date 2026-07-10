output "dataset_ids" {
  description = "Created BigQuery dataset ids."
  value       = [for d in google_bigquery_dataset.this : d.dataset_id]
}
