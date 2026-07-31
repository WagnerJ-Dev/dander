output "provider_resource_name" {
  description = "Resource name supplied to google-github-actions/auth."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "service_account_email" {
  description = "Deployment service account impersonated by GitHub Actions."
  value       = google_service_account.deployer.email
}
