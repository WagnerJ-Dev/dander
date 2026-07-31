variable "project_id" {
  type        = string
  description = "GCP project id receiving the Dander datasets."
}

variable "bootstrap_billing_account_id" {
  type        = string
  description = "Billing account where the bootstrap identity may manage Terraform budget resources."
  default     = ""

  validation {
    condition     = var.bootstrap_billing_account_id == "" || can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.bootstrap_billing_account_id))
    error_message = "Bootstrap billing account must be empty or use XXXXXX-XXXXXX-XXXXXX format."
  }
}

variable "region" {
  type        = string
  description = "Default GCP region for provider resources."
  default     = "us-central1"
}

variable "bigquery_location" {
  type        = string
  description = "BigQuery data location."
  default     = "US"
}

variable "datasets" {
  type        = list(string)
  description = "BigQuery datasets created for the first runtime slice."
  default     = ["raw", "staging", "marts"]
}

variable "enable_scheduled_job" {
  type        = bool
  description = "Provision the public-ingestion Cloud Run Job and daily scheduler."
  default     = false
}

variable "billing_account_id" {
  type        = string
  description = "Billing account id used for the runtime's read-only budget preflight."
  default     = ""
}

variable "runtime_container_image" {
  type        = string
  description = "Immutable Artifact Registry image reference for the Cloud Run Job."
  default     = ""
}

variable "scheduler_paused" {
  type        = bool
  description = "Keep the daily scheduler paused until a manual job execution succeeds."
  default     = true
}

variable "runtime_publish_dataplex" {
  type        = bool
  description = "Publish Dataplex aspects from the hosted job; stored metadata may be billable."
  default     = false
}

variable "secret_ids" {
  type        = set(string)
  description = "Secret Manager containers to create; secret values are never managed by Terraform."
  default     = []

  validation {
    condition = alltrue([
      for secret_id in var.secret_ids : can(regex("^[A-Za-z][A-Za-z0-9_-]{0,254}$", secret_id))
    ])
    error_message = "Secret ids must begin with a letter and contain only letters, numbers, '_' or '-'."
  }
}

variable "github_repository" {
  type        = string
  description = "GitHub owner/repository allowed to use deployment WIF; empty disables WIF."
  default     = ""

  validation {
    condition     = var.github_repository == "" || can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "GitHub repository must be empty or use owner/repository format."
  }
}

variable "github_ref" {
  type        = string
  description = "Exact Git ref allowed to use deployment WIF."
  default     = "refs/heads/main"

  validation {
    condition     = can(regex("^refs/(heads|tags)/[A-Za-z0-9._/-]+$", var.github_ref))
    error_message = "GitHub ref must be an exact refs/heads/... or refs/tags/... value."
  }
}

variable "enable_cost_guard" {
  type        = bool
  description = "Provision the project-scoped budget and simulation-first kill switch."
  default     = false
}

variable "cost_guard_budget_name" {
  type        = string
  description = "Display name expected by the budget verifier and kill-switch handler."
  default     = "dander-sbx-cap"
}

variable "cost_guard_budget_amount" {
  type        = number
  description = "Maximum configured USD budget; Dander rejects values above five."
  default     = 5

  validation {
    condition     = var.cost_guard_budget_amount > 0 && var.cost_guard_budget_amount <= 5
    error_message = "Cost-guard budget must be greater than zero and no greater than USD 5."
  }
}

variable "cost_guard_simulate" {
  type        = bool
  description = "Log an over-budget action without unlinking billing."
  default     = true
}

variable "cost_guard_source_bucket" {
  type        = string
  description = "Existing GCS bucket used to stage the Cloud Run function source archive."
  default     = ""
}
