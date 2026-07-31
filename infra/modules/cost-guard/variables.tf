variable "project_id" {
  type        = string
  description = "Disposable GCP project protected by the cost guard."
}

variable "region" {
  type        = string
  description = "Region receiving the Gen 2 Cloud Run function."
}

variable "billing_account_id" {
  type        = string
  description = "Billing account containing the project-scoped budget."
}

variable "source_bucket" {
  type        = string
  description = "Existing GCS bucket used for the function source archive."
}

variable "function_source_dir" {
  type        = string
  description = "Local directory containing the tested Python function."
}

variable "budget_name" {
  type        = string
  description = "Budget display name accepted by the function."
}

variable "budget_amount" {
  type        = number
  description = "Project-scoped USD budget amount."

  validation {
    condition     = var.budget_amount > 0 && var.budget_amount <= 5
    error_message = "Budget amount must be greater than zero and no greater than USD 5."
  }
}

variable "simulate" {
  type        = bool
  description = "Whether over-budget notifications only simulate billing detachment."
  default     = true
}
