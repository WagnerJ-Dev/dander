output "service_account_email" {
  description = "Email of the identity intended for approved Terraform bootstrap runs."
  value       = google_service_account.bootstrap.email
}

output "service_account_name" {
  description = "Full resource name of the bootstrap identity."
  value       = google_service_account.bootstrap.name
}
