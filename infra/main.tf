module "bigquery" {
  source = "./modules/bigquery"

  project_id = var.project_id
  location   = var.bigquery_location
  datasets   = var.datasets
}

module "scheduled_job" {
  count  = var.enable_scheduled_job ? 1 : 0
  source = "./modules/scheduled-job"

  project_id           = var.project_id
  region               = var.region
  billing_account_id   = var.billing_account_id
  container_image      = var.runtime_container_image
  scheduler_paused     = var.scheduler_paused
  publish_dataplex     = var.runtime_publish_dataplex
  runtime_source       = var.runtime_source
  runtime_model        = var.runtime_model
  runtime_build_models = var.runtime_build_models
  runtime_secret_id    = var.runtime_secret_id
  runtime_secret_env   = var.runtime_secret_env
  transform_dataset_ids = setsubtract(
    toset(var.datasets),
    toset(["raw"]),
  )
}

module "secret_manager" {
  count  = length(var.secret_ids) > 0 ? 1 : 0
  source = "./modules/secret-manager"

  project_id = var.project_id
  secret_ids = setunion(
    var.secret_ids,
    var.runtime_secret_id == "" ? toset([]) : toset([var.runtime_secret_id]),
  )
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

module "cost_guard" {
  count  = var.enable_cost_guard ? 1 : 0
  source = "./modules/cost-guard"
  providers = {
    google         = google
    google.billing = google.billing
  }

  project_id          = var.project_id
  region              = var.region
  billing_account_id  = var.billing_account_id
  source_bucket       = var.cost_guard_source_bucket
  function_source_dir = "${path.root}/functions/stop_billing"
  budget_name         = var.cost_guard_budget_name
  budget_amount       = var.cost_guard_budget_amount
  simulate            = var.cost_guard_simulate
}

check "cost_guard_inputs" {
  assert {
    condition = !var.enable_cost_guard || (
      var.billing_account_id != "" && var.cost_guard_source_bucket != ""
    )
    error_message = "The cost guard requires billing_account_id and cost_guard_source_bucket."
  }
}
