variable "project_id" {
  type        = string
  description = "GCP project receiving the secret containers."
}

variable "secret_ids" {
  type        = set(string)
  description = "Secret container ids. This module never manages secret versions."
}

variable "accessor_members" {
  type        = set(string)
  description = "Service-account members allowed to access only these secrets."
  default     = []

  validation {
    condition     = alltrue([for member in var.accessor_members : startswith(member, "serviceAccount:")])
    error_message = "Secret accessors must be serviceAccount: IAM members."
  }
}
