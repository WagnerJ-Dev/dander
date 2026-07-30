module "bigquery" {
  source = "./modules/bigquery"

  project_id = var.project_id
  location   = var.bigquery_location
  datasets   = var.datasets
}

module "scheduled_job" {
  count  = var.enable_scheduled_job ? 1 : 0
  source = "./modules/scheduled-job"

  project_id         = var.project_id
  region             = var.region
  billing_account_id = var.billing_account_id
  container_image    = var.runtime_container_image
  scheduler_paused   = var.scheduler_paused
}

module "secret_manager" {
  count  = length(var.secret_ids) > 0 ? 1 : 0
  source = "./modules/secret-manager"

  project_id = var.project_id
  secret_ids = var.secret_ids
  accessor_members = var.enable_scheduled_job ? [
    "serviceAccount:${module.scheduled_job[0].runtime_service_account}",
  ] : []
}

module "github_wif" {
  count  = var.github_repository != "" && var.enable_scheduled_job ? 1 : 0
  source = "./modules/github-wif"

  project_id          = var.project_id
  region              = var.region
  artifact_repository = module.scheduled_job[0].artifact_repository_id
  github_repository   = var.github_repository
  github_ref          = var.github_ref
  service_account_ids = [
    module.scheduled_job[0].runtime_service_account_name,
    module.scheduled_job[0].scheduler_service_account_name,
  ]
}

check "github_wif_requires_runtime" {
  assert {
    condition     = var.github_repository == "" || var.enable_scheduled_job
    error_message = "github_repository requires enable_scheduled_job=true."
  }
}
