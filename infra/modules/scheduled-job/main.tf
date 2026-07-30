locals {
  runtime_account   = "dander-runtime"
  scheduler_account = "dander-scheduler"
  job_name          = "dander-greenhouse-public"
}

resource "google_project_service" "required" {
  for_each = toset(concat([
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
    "run.googleapis.com",
  ], var.publish_dataplex ? ["dataplex.googleapis.com"] : []))

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "dander"
  description   = "Dander runtime container images"
  format        = "DOCKER"
  labels = {
    module = "scheduled-job"
    owner  = "dander"
  }

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "86400s"
    }
  }

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = local.runtime_account
  display_name = "Dander ingestion runtime"
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = local.scheduler_account
  display_name = "Dander Cloud Scheduler invoker"
}

resource "google_project_iam_member" "runtime_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_pubsub_viewer" {
  project = var.project_id
  role    = "roles/pubsub.viewer"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_bigquery_dataset_iam_member" "runtime_writer" {
  project    = var.project_id
  dataset_id = var.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_bigquery_dataset_iam_member" "runtime_transform_writer" {
  for_each = var.transform_dataset_ids

  project    = var.project_id
  dataset_id = each.value
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_catalog_editor" {
  count = var.publish_dataplex ? 1 : 0

  project = var.project_id
  role    = "roles/dataplex.catalogEditor"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_billing_account_iam_member" "runtime_budget_viewer" {
  billing_account_id = var.billing_account_id
  role               = "roles/billing.viewer"
  member             = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_job" "ingestion" {
  project             = var.project_id
  name                = local.job_name
  location            = var.region
  deletion_protection = false
  labels = {
    module = "scheduled-job"
    owner  = "dander"
  }

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.runtime.email
      timeout         = "300s"
      max_retries     = 1

      containers {
        image = var.container_image
        args = concat(
          [
            "run",
            "greenhouse_job_board",
            "--guarded-free-tier",
            "--build-models",
            "--models-dir",
            "/app/models",
            "--select-model",
            "stg_greenhouse__jobs",
            "--catalog-output",
            "/tmp/dander-catalog.json",
          ],
          var.publish_dataplex ? ["--publish-dataplex"] : [],
        )

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET_RAW"
          value = var.dataset_id
        }
        env {
          name  = "DANDER_PRINCIPAL"
          value = google_service_account.runtime.email
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.images,
    google_bigquery_dataset_iam_member.runtime_writer,
    google_bigquery_dataset_iam_member.runtime_transform_writer,
    google_billing_account_iam_member.runtime_budget_viewer,
    google_project_iam_member.runtime_job_user,
    google_project_iam_member.runtime_pubsub_viewer,
    google_project_iam_member.runtime_catalog_editor,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_job.ingestion.location
  name     = google_cloud_run_v2_job.ingestion.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "ingestion" {
  project          = var.project_id
  region           = var.region
  name             = "${local.job_name}-daily"
  description      = "Run the public Greenhouse ingestion once daily"
  schedule         = var.schedule
  time_zone        = var.time_zone
  paused           = var.scheduler_paused
  attempt_deadline = "180s"

  retry_config {
    retry_count          = 1
    min_backoff_duration = "30s"
    max_backoff_duration = "60s"
    max_doublings        = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.ingestion.name}:run"
    body        = base64encode("{}")
    headers = {
      "Content-Type" = "application/json"
    }

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.scheduler_invoker,
    google_project_service.required,
  ]
}
