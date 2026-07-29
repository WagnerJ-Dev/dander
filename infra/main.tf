module "bigquery" {
  source = "./modules/bigquery"

  project_id = var.project_id
  location   = var.bigquery_location
  datasets   = var.datasets
}
