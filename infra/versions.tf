terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Remote state — never commit local state (steering/01-security.md).
  # Uncomment and set the bucket per environment:
  # backend "gcs" {
  #   bucket = "REPLACE_ME-tfstate"
  #   prefix = "dander/state"
  # }
}
