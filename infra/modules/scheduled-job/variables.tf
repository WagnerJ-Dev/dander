variable "project_id" {
  type        = string
  description = "GCP project that owns the runtime resources."
}

variable "region" {
  type        = string
  description = "GCP region for Artifact Registry, Cloud Run, and Cloud Scheduler."
}

variable "billing_account_id" {
  type        = string
  description = "Billing account inspected by the guarded free-tier preflight."
}

variable "container_image" {
  type        = string
  description = "Immutable Artifact Registry image reference, including its sha256 digest."

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must be an immutable image reference ending in @sha256:<64 lowercase hex characters>."
  }
}

variable "dataset_id" {
  type        = string
  description = "BigQuery dataset the runtime may edit."
  default     = "raw"
}

variable "schedule" {
  type        = string
  description = "Cron schedule for public ingestion."
  default     = "0 9 * * *"
}

variable "time_zone" {
  type        = string
  description = "IANA time zone used to interpret the cron schedule."
  default     = "America/New_York"
}

variable "scheduler_paused" {
  type        = bool
  description = "Keep the schedule paused until a manual execution has succeeded."
  default     = true
}
