variable "project_id" {
  type        = string
  description = "GCP project receiving the secret containers."
}

variable "secret_ids" {
  type        = set(string)
  description = "Secret container ids. This module never manages secret versions."
}

variable "accessors_by_secret" {
  type        = map(set(string))
  description = "Service-account members allowed to access each named secret."
  default     = {}

  validation {
    condition = alltrue(flatten([
      for secret_id, members in var.accessors_by_secret : [
        contains(var.secret_ids, secret_id),
        alltrue([for member in members : startswith(member, "serviceAccount:")]),
      ]
    ]))
    error_message = "Secret accessor keys must name managed secrets and members must be serviceAccount: IAM members."
  }
}
