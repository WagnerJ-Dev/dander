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

variable "transform_dataset_ids" {
  type        = set(string)
  description = "Additional datasets the hosted transform tail may edit."
  default     = ["staging", "marts"]
}

variable "publish_dataplex" {
  type        = bool
  description = "Publish metadata aspects after hosted transforms; stored metadata may be billable."
  default     = false
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

variable "runtime_source" {
  type        = string
  description = "Connector source name passed to the hosted Dander job."
  default     = "greenhouse_job_board"

  validation {
    condition     = can(regex("^[A-Za-z_][A-Za-z0-9_-]*$", var.runtime_source))
    error_message = "runtime_source must be a valid Dander connector name."
  }
}

variable "runtime_model" {
  type        = string
  description = "Transform model selected by the hosted Dander job."
  default     = "stg_greenhouse__jobs"

  validation {
    condition     = can(regex("^[A-Za-z_][A-Za-z0-9_-]*$", var.runtime_model))
    error_message = "runtime_model must be a valid Dander model name."
  }
}

variable "runtime_build_models" {
  type        = bool
  description = "Run hosted transform builds/tests after ingestion."
  default     = true
}

variable "runtime_secret_id" {
  type        = string
  description = "Optional Secret Manager container exposed to the connector."
  default     = ""
}

variable "runtime_secret_env" {
  type        = string
  description = "Environment variable containing the Secret Manager resource reference."
  default     = "HUBSPOT_PRIVATE_APP_TOKEN"

  validation {
    condition     = can(regex("^[A-Z][A-Z0-9_]*$", var.runtime_secret_env))
    error_message = "runtime_secret_env must be an uppercase environment variable name."
  }
}
