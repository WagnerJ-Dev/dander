terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }

  # Values are supplied by `dander init` via `terraform init -backend-config`; Terraform backends
  # cannot use input variables.
  backend "gcs" {}
}

provider "google" {
  project                     = var.project_id
  region                      = var.region
  impersonate_service_account = var.bootstrap_service_account
}

provider "google" {
  alias                       = "billing"
  project                     = var.project_id
  region                      = var.region
  billing_project             = var.project_id
  user_project_override       = true
  impersonate_service_account = var.bootstrap_service_account
}

check "bootstrap_impersonation_required" {
  assert {
    condition     = var.bootstrap_service_account != ""
    error_message = "Platform Terraform must run by impersonating dander-bootstrap."
  }
}
