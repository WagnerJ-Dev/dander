locals {
  account_id = "dander-bootstrap"
}

resource "google_service_account" "bootstrap" {
  project      = var.project_id
  account_id   = local.account_id
  display_name = "Dander Terraform bootstrap"
}

resource "google_project_iam_member" "bootstrap" {
  for_each = var.bootstrap_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.bootstrap.email}"
}

resource "google_billing_account_iam_member" "bootstrap_budget_admin" {
  count = var.bootstrap_billing_account_id == "" ? 0 : 1

  billing_account_id = var.bootstrap_billing_account_id
  role               = "roles/billing.costsManager"
  member             = "serviceAccount:${google_service_account.bootstrap.email}"
}
