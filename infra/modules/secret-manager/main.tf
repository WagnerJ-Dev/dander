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
    for binding in flatten([
      for secret_id, members in var.accessors_by_secret : [
        for member in members : {
          key    = "${secret_id}|${member}"
          secret = secret_id
          member = member
        }
      ]
    ]) : binding.key => binding
  }
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each = local.accessor_bindings

  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value.secret].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value.member
}
