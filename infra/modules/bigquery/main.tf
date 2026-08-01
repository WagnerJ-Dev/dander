# Creates raw, staging, marts, and the durable metadata/control dataset.
resource "google_bigquery_dataset" "this" {
  for_each = toset(var.datasets)

  dataset_id = each.value
  project    = var.project_id
  location   = var.location

  labels = {
    owner  = "dander"
    module = "bigquery"
  }
}
