variable "project_id" {
  type        = string
  description = "Billing-linked GCP project that will host Dander."
}

variable "region" {
  type        = string
  description = "Default region used by the administrative bootstrap."
  default     = "us-central1"
}

variable "state_bucket" {
  type        = string
  description = "Globally unique GCS bucket name for the main platform Terraform state."
}

variable "state_location" {
  type        = string
  description = "GCS location for the remote Terraform state bucket."
  default     = "US"
}

variable "bootstrap_service_account_id" {
  type        = string
  description = "Account id for the dedicated platform Terraform identity."
  default     = "dander-bootstrap"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.bootstrap_service_account_id))
    error_message = "Bootstrap service-account id must be 6-30 lowercase letters, numbers, or hyphens."
  }
}

variable "admin_member" {
  type        = string
  description = "Approved caller allowed to impersonate the bootstrap service account."

  validation {
    condition     = can(regex("^(user|serviceAccount|group):[^\\r\\n]+$", var.admin_member))
    error_message = "admin_member must be a user:, serviceAccount:, or group: principal."
  }
}

variable "billing_account_id" {
  type        = string
  description = "Optional billing account receiving budget-admin access for the bootstrap identity."
  default     = ""

  validation {
    condition     = var.billing_account_id == "" || can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "Billing account must be empty or use XXXXXX-XXXXXX-XXXXXX format."
  }
}

variable "github_repository" {
  type        = string
  description = "Optional GitHub owner/repository allowed to authenticate as the proof administrator."
  default     = ""

  validation {
    condition     = var.github_repository == "" || can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "GitHub repository must be empty or use owner/repository format."
  }
}

variable "github_ref" {
  type        = string
  description = "Exact GitHub branch or tag ref allowed to authenticate."
  default     = "refs/heads/main"

  validation {
    condition     = can(regex("^refs/(heads|tags)/[A-Za-z0-9._/-]+$", var.github_ref))
    error_message = "GitHub ref must be an exact refs/heads/... or refs/tags/... value."
  }
}
