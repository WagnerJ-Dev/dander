variable "project_id" {
  type        = string
  description = "GCP project hosting the Druff interface."
}

variable "region" {
  type        = string
  description = "Cloud Run service region."
}

variable "container_image" {
  type        = string
  description = "Immutable source-free Druff image."

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must be an immutable image reference ending in @sha256:<64 lowercase hex characters>."
  }
}
