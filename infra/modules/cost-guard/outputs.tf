output "budget_name" {
  description = "Budget display name."
  value       = google_billing_budget.project.display_name
}

output "function_name" {
  description = "Gen 2 Cloud Run function resource name."
  value       = google_cloudfunctions2_function.stop_billing.name
}

output "pubsub_topic" {
  description = "Budget notification Pub/Sub topic."
  value       = google_pubsub_topic.budget.id
}
