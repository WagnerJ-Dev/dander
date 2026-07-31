locals {
  required_services = toset([
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "serviceusage.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
  ])
  provisioning_roles = toset([
    "roles/artifactregistry.admin",
    "roles/bigquery.admin",
    "roles/cloudfunctions.admin",
    "roles/cloudscheduler.admin",
    "roles/dataplex.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/pubsub.admin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/run.admin",
    "roles/secretmanager.admin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/storage.admin",
  ])
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "terraform_state" {
  project                     = var.project_id
  name                        = var.state_bucket
  location                    = var.state_location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  labels = {
    managed-by = "dander"
    purpose    = "terraform-state"
  }

  depends_on = [google_project_service.required]
}

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "dander"
  description   = "Dander runtime container images"
  format        = "DOCKER"
  labels = {
    managed-by = "dander"
    purpose    = "runtime-images"
  }

  depends_on = [google_project_service.required]
}

resource "google_service_account" "bootstrap" {
  project      = var.project_id
  account_id   = var.bootstrap_service_account_id
  display_name = "Dander Terraform bootstrap"

  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "provisioning" {
  for_each = local.provisioning_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.bootstrap.email}"
}

resource "google_service_account_iam_member" "admin_impersonation" {
  service_account_id = google_service_account.bootstrap.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = var.admin_member
}

resource "google_billing_account_iam_member" "budget_admin" {
  count = var.billing_account_id == "" ? 0 : 1

  billing_account_id = var.billing_account_id
  role               = "roles/billing.costsManager"
  member             = "serviceAccount:${google_service_account.bootstrap.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  count = var.github_repository == "" ? 0 : 1

  project                   = var.project_id
  workload_identity_pool_id = "dander-proof-github"
  display_name              = "Dander proof GitHub"
  depends_on                = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count = var.github_repository == "" ? 0 : 1

  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "Dander proof GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == '${var.github_ref}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "github" {
  count = var.github_repository == "" ? 0 : 1

  project      = var.project_id
  account_id   = "dander-proof-github"
  display_name = "Dander proof GitHub administrator"
}

resource "google_service_account_iam_member" "github_impersonates_bootstrap" {
  count = var.github_repository == "" ? 0 : 1

  service_account_id = google_service_account.bootstrap.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_repository}"
}

resource "google_service_account_iam_member" "github_wif_user" {
  count = var.github_repository == "" ? 0 : 1

  service_account_id = google_service_account.github[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_repository}"
}
