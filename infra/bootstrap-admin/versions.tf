terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # The bucket and prefix are supplied by the administrative wrapper at init time. Credentials
  # come from the operator's Google authentication context and are never stored in configuration.
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}
