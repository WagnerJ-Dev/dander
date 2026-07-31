variable "project_id" {
  type        = string
  description = "GCP project receiving the bootstrap identity."
}

variable "bootstrap_roles" {
  type        = set(string)
  description = "Project-level roles for the short-lived Terraform bootstrap identity."
  default = [
    "roles/artifactregistry.admin",
    "roles/bigquery.admin",
    "roles/cloudfunctions.admin",
    "roles/cloudscheduler.admin",
    "roles/dataplex.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/pubsub.admin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/run.admin",
    "roles/secretmanager.admin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/storage.admin",
  ]
}

variable "bootstrap_billing_account_id" {
  type        = string
  description = "Optional billing account where the bootstrap identity receives budget-admin access."
  default     = ""
}
