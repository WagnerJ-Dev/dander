locals {
  required_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
  ])
  function_name = "dander-stop-billing"
  topic_name    = "dander-stop-billing"
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_project_service" "required" {
  for_each = local.required_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_pubsub_topic" "budget" {
  project = var.project_id
  name    = local.topic_name

  depends_on = [google_project_service.required]
}

resource "google_pubsub_topic_iam_member" "billing_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.budget.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:billing-budget-alerts@system.gserviceaccount.com"
}

resource "google_service_account" "function" {
  project      = var.project_id
  account_id   = "dander-cost-guard"
  display_name = "Dander cost guard"
}

resource "google_service_account" "builder" {
  project      = var.project_id
  account_id   = "dander-function-builder"
  display_name = "Dander function builder"
}

resource "google_project_iam_member" "builder" {
  for_each = toset([
    "roles/cloudbuild.builds.builder",
    "roles/run.invoker",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_storage_bucket_iam_member" "builder_source_reader" {
  bucket = var.source_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_project_iam_member" "billing_project_manager" {
  project = var.project_id
  role    = "roles/billing.projectManager"
  member  = "serviceAccount:${google_service_account.function.email}"
}

resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.function.email}"
}

resource "google_billing_account_iam_member" "billing_viewer" {
  billing_account_id = var.billing_account_id
  role               = "roles/billing.viewer"
  member             = "serviceAccount:${google_service_account.function.email}"
}

data "archive_file" "source" {
  type        = "zip"
  source_dir  = var.function_source_dir
  output_path = "${path.root}/.terraform/dander-cost-guard.zip"
  excludes    = ["__pycache__", "__pycache__/*"]
}

resource "google_storage_bucket_object" "source" {
  name   = "dander/functions/stop-billing-${data.archive_file.source.output_md5}.zip"
  bucket = var.source_bucket
  source = data.archive_file.source.output_path
}

resource "google_cloudfunctions2_function" "stop_billing" {
  project     = var.project_id
  location    = var.region
  name        = local.function_name
  description = "Simulation-first Dander budget kill switch"

  build_config {
    runtime         = "python312"
    entry_point     = "stop_billing"
    service_account = google_service_account.builder.name
    source {
      storage_source {
        bucket = var.source_bucket
        object = google_storage_bucket_object.source.name
      }
    }
  }

  service_config {
    min_instance_count    = 0
    max_instance_count    = 1
    available_memory      = "256M"
    timeout_seconds       = 60
    ingress_settings      = "ALLOW_INTERNAL_ONLY"
    service_account_email = google_service_account.function.email
    environment_variables = {
      TARGET_PROJECT_ID     = var.project_id
      EXPECTED_BUDGET_NAME  = var.budget_name
      SIMULATE_DEACTIVATION = tostring(var.simulate)
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.budget.id
    retry_policy   = "RETRY_POLICY_DO_NOT_RETRY"
  }

  depends_on = [
    google_billing_account_iam_member.billing_viewer,
    google_project_iam_member.builder,
    google_project_iam_member.billing_project_manager,
    google_project_iam_member.log_writer,
    google_project_service.required,
    google_storage_bucket_iam_member.builder_source_reader,
  ]
}

resource "google_billing_budget" "project" {
  provider = google.billing

  billing_account = "billingAccounts/${var.billing_account_id}"
  display_name    = var.budget_name

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(floor(var.budget_amount))
      nanos         = (var.budget_amount - floor(var.budget_amount)) * 1000000000
    }
  }

  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  all_updates_rule {
    pubsub_topic                   = google_pubsub_topic.budget.id
    schema_version                 = "1.0"
    disable_default_iam_recipients = false
  }

  depends_on = [
    google_project_service.required,
    google_pubsub_topic_iam_member.billing_publisher,
  ]
}
