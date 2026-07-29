variable "project_id" {
  type        = string
  description = "GCP project id receiving the Dander datasets."
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
