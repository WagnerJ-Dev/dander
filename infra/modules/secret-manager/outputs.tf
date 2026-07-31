output "secret_resources" {
  description = "Map of secret ids to resource names."
  value       = { for id, secret in google_secret_manager_secret.this : id => secret.name }
}
