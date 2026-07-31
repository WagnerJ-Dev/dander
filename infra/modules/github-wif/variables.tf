variable "project_id" {
  type        = string
  description = "GCP project receiving the deployment identity."
}

variable "region" {
  type        = string
  description = "Region containing the Dander Artifact Registry repository."
}

variable "artifact_repository" {
  type        = string
  description = "Artifact Registry repository the deployer may write."
}

variable "github_repository" {
  type        = string
  description = "Exact GitHub owner/repository allowed to authenticate."
}

variable "github_ref" {
  type        = string
  description = "Exact Git ref allowed to authenticate."
}

variable "service_account_ids" {
  type        = set(string)
  description = "Full resource names of service accounts the deployer may act as."
  default     = []
}
