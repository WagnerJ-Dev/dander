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
  description = "BigQuery dataset every runtime may edit for ingestion and control state."
  default     = "raw"
}

variable "transform_dataset_ids" {
  type        = set(string)
  description = "Additional datasets hosted transforms may edit."
  default     = ["staging", "marts"]
}

variable "pipelines" {
  description = "Expanded hosted pipeline definitions keyed by stable Dander pipeline id."
  type = map(object({
    job_name                     = string
    runtime_service_account_id   = string
    scheduler_service_account_id = string
    source                       = string
    models                       = list(string)
    build_models                 = bool
    publish_dataplex             = bool
    schedule                     = string
    time_zone                    = string
    paused                       = bool
    secret_env                   = map(string)
  }))

  validation {
    condition = alltrue([
      for id, pipeline in var.pipelines :
      can(regex("^[a-z][a-z0-9_-]{1,62}$", id)) &&
      can(regex("^[a-z][a-z0-9-]{0,61}[a-z0-9]$", pipeline.job_name)) &&
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", pipeline.runtime_service_account_id)) &&
      can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", pipeline.scheduler_service_account_id)) &&
      can(regex("^[A-Za-z_][A-Za-z0-9_-]*$", pipeline.source)) &&
      length(pipeline.models) > 0 &&
      alltrue([for model in pipeline.models : can(regex("^[A-Za-z_][A-Za-z0-9_-]*$", model))]) &&
      length(trimspace(pipeline.schedule)) > 0 &&
      length(trimspace(pipeline.time_zone)) > 0 &&
      alltrue([
        for env_name, secret_id in pipeline.secret_env :
        can(regex("^[A-Z][A-Z0-9_]*$", env_name)) &&
        can(regex("^[A-Za-z][A-Za-z0-9_-]{0,254}$", secret_id))
      ])
    ])
    error_message = "Every pipeline must use safe ids, a non-empty model selection and schedule, and valid secret bindings."
  }
}
