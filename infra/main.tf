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
