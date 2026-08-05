resource "google_service_account" "druff" {
  project      = var.project_id
  account_id   = "dander-druff"
  display_name = "Dander Druff interface"
}

resource "google_cloud_run_v2_service" "druff" {
  project              = var.project_id
  name                 = "dander-druff"
  location             = var.region
  deletion_protection  = false
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = true

  labels = {
    module = "druff"
    owner  = "dander"
  }

  template {
    service_account = google_service_account.druff.email

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = false
      }

      startup_probe {
        failure_threshold = 6
        period_seconds    = 5
        timeout_seconds   = 2

        http_get {
          path = "/"
          port = 8080
        }
      }
    }
  }
}
