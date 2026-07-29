terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Values are supplied by `dander init` via `terraform init -backend-config`; Terraform backends
  # cannot use input variables.
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}
