"""Static Terraform contracts for additive hosted pipelines."""

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_root_passes_pipeline_map_and_scopes_secrets_per_runtime() -> None:
    root = (ROOT / "infra/main.tf").read_text(encoding="utf-8")
    secret_module = (ROOT / "infra/modules/secret-manager/main.tf").read_text(encoding="utf-8")

    assert "pipelines           = var.pipelines" in root
    assert "failure_alert_email = var.failure_alert_email" in root
    assert "pipeline_secret_accessors" in root
    assert "accessors_by_secret = local.pipeline_secret_accessors" in root
    assert "setproduct(var.secret_ids" not in secret_module
    assert "depends_on = [module.bigquery]" in root
    assert 'toset(["raw"])' in root


def test_scheduled_module_preserves_greenhouse_and_creates_each_pipeline() -> None:
    module = (ROOT / "infra/modules/scheduled-job/main.tf").read_text(encoding="utf-8")

    assert 'to   = google_cloud_run_v2_job.ingestion["greenhouse_jobs"]' in module
    assert 'to   = google_cloud_scheduler_job.ingestion["greenhouse_jobs"]' in module
    assert 'resource "google_cloud_run_v2_job" "ingestion" {' in module
    assert 'resource "google_cloud_scheduler_job" "ingestion" {' in module
    assert 'resource "google_monitoring_notification_channel" "pipeline_failures" {' in module
    assert 'resource "google_monitoring_alert_policy" "pipeline_failure" {' in module
    assert 'metric.type = \\"run.googleapis.com/job/completed_execution_count\\"' in module
    assert 'metric.label.\\"result\\" = \\"failed\\"' in module
    assert module.count("for_each = var.pipelines") >= 8
    assert '["run", each.key, "--config", "/app/dander.yaml", "--guarded-free-tier"]' in module


def test_container_carries_the_project_manifest() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "COPY dander.yaml ./dander.yaml" in dockerfile
    assert "!dander.yaml" in dockerignore


def test_bootstrap_identity_can_manage_monitoring_alerts() -> None:
    bootstrap = (ROOT / "infra/bootstrap-admin/main.tf").read_text(encoding="utf-8")

    assert '"monitoring.googleapis.com"' in bootstrap
    assert '"roles/monitoring.editor"' in bootstrap
