resource "google_project_service" "secret_manager" {
  project            = var.project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_secret_manager_secret" "this" {
  for_each = var.secret_ids

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }

  labels = {
    managed-by = "dander"
  }

  depends_on = [google_project_service.secret_manager]
}

locals {
  accessor_bindings = {
    for pair in setproduct(var.secret_ids, var.accessor_members) :
    "${pair[0]}|${pair[1]}" => {
      secret = pair[0]
      member = pair[1]
    }
  }
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = local.accessor_bindings

  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value.secret].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value.member
}
