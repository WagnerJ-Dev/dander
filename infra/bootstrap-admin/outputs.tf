output "state_bucket" {
  description = "Remote GCS state bucket created by stage zero."
  value       = google_storage_bucket.terraform_state.name
}

output "bootstrap_service_account" {
  description = "Service account impersonated by the main platform Terraform root."
  value       = google_service_account.bootstrap.email
}

output "impersonation_member" {
  description = "Approved caller granted service-account token creation."
  value       = var.admin_member
}

output "github_workload_identity_provider" {
  description = "Optional WIF provider for the protected live-proof workflow."
  value       = var.github_repository == "" ? null : google_iam_workload_identity_pool_provider.github[0].name
}

output "github_service_account" {
  description = "Optional WIF service account that may impersonate dander-bootstrap."
  value       = var.github_repository == "" ? null : google_service_account.github[0].email
}
