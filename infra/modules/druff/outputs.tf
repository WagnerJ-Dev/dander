output "service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.druff.name
}

output "url" {
  description = "Public HTTPS URL for the presentation-only Druff interface."
  value       = google_cloud_run_v2_service.druff.uri
}
