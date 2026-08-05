"""Static Terraform contracts for the optional Druff interface."""

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_druff_is_optional_source_free_and_separate_from_pipeline_authority() -> None:
    root = (ROOT / "infra/main.tf").read_text(encoding="utf-8")
    module = (ROOT / "infra/modules/druff/main.tf").read_text(encoding="utf-8")
    normalized = "\n".join(" ".join(line.split()) for line in module.splitlines())

    assert 'count  = var.druff_container_image == "" ? 0 : 1' in root
    assert "container_image = var.druff_container_image" in root
    assert "depends_on = [module.scheduled_job]" in root
    assert 'check "druff_requires_runtime"' in root
    assert 'resource "google_cloud_run_v2_service" "druff"' in module
    assert "invoker_iam_disabled = true" in normalized
    assert "min_instance_count = 0" in normalized
    assert "max_instance_count = 1" in normalized
    assert "service_account = google_service_account.druff.email" in normalized
    assert "roles/" not in module
    assert "secret" not in module.lower()
    assert "bigquery" not in module.lower()
    assert "scheduler" not in module.lower()
    assert "google_project_service" not in module
    assert "@sha256" in (ROOT / "infra/modules/druff/variables.tf").read_text(encoding="utf-8")
