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
