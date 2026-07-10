variable "project_id" {
  type        = string
  description = "GCP project id. Never hard-coded — supplied per environment."
}

variable "location" {
  type        = string
  description = "BigQuery dataset location."
  default     = "US"
}

variable "datasets" {
  type        = list(string)
  description = "Dataset ids to create."
  default     = ["raw", "staging", "marts"]
}
