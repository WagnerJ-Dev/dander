"""Focused proof for the corrected Phase 3B ownership scope."""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ADDRESS = "module.scheduled_job[0].google_artifact_registry_repository.images"
CONFIG_REMOVED_ADDRESS = "module.scheduled_job.google_artifact_registry_repository.images"
STAGE_ZERO_REPOSITORY_ADDRESS = "google_artifact_registry_repository.images"
STATE_BUCKET_ADDRESS = "google_storage_bucket.terraform_state"
PLATFORM_STATE_GENERATION = "1785368475607577"
STAGE_ZERO_STATE_GENERATION = "1785527056966752"
REPOSITORY_ID = "projects/dander-sbx-harrison-20260729/locations/us-central1/repositories/dander"


ROOT = Path(__file__).parents[2]


def _removed_blocks() -> list[str]:
    source = (ROOT / "infra/ownership-cutover.tf").read_text()
    return re.findall(r"removed\s*\{.*?\n\}", source, flags=re.DOTALL)


def test_exactly_one_preserving_removed_binding_is_declared() -> None:
    blocks = _removed_blocks()

    assert len(blocks) == 1
    assert (
        blocks[0]
        == """removed {
  # The live state address is module.scheduled_job[0].google_artifact_registry_repository.images.
  # Terraform's removed.from syntax requires the counted module call without [0].
  from = module.scheduled_job.google_artifact_registry_repository.images

  lifecycle {
    destroy = false
  }
}"""
    )


def test_scope_matches_stage_zero_and_excludes_bucket_and_broad_removal() -> None:
    source = (ROOT / "infra/ownership-cutover.tf").read_text()
    stage_zero = (ROOT / "infra/bootstrap-admin/main.tf").read_text()
    platform = (ROOT / "infra/main.tf").read_text()
    scheduled_job = (ROOT / "infra/modules/scheduled-job/main.tf").read_text()

    assert REPOSITORY_ADDRESS in source
    assert CONFIG_REMOVED_ADDRESS in source
    assert 'resource "google_artifact_registry_repository" "images"' in stage_zero
    assert 'repository_id = "dander"' in stage_zero
    assert 'format        = "DOCKER"' in stage_zero
    assert "google_artifact_registry_repository.images" not in platform
    assert 'data "google_artifact_registry_repository" "images"' in scheduled_job
    assert 'count  = var.enable_scheduled_job ? 1 : 0' in platform
    assert STATE_BUCKET_ADDRESS not in source
    assert "from = module.scheduled_job[0]" not in source
    assert "removed {\n  # The live state address" in source


def test_documented_live_identity_evidence_is_sanitized_and_complete() -> None:
    documentation = (ROOT / "docs/phase3b-ownership.md").read_text()

    for expected in (
        REPOSITORY_ADDRESS,
        STAGE_ZERO_REPOSITORY_ADDRESS,
        PLATFORM_STATE_GENERATION,
        STAGE_ZERO_STATE_GENERATION,
        REPOSITORY_ID,
        "binding exists for `google_storage_bucket.terraform_state`.",
        "no cost-guard resource is selected.",
    ):
        assert expected in documentation


def test_only_repository_binding_is_selected_and_preserved() -> None:
    source = (ROOT / "infra/ownership-cutover.tf").read_text()

    assert source.count("removed {") == 1
    assert source.count("destroy = false") == 1
    assert "from = module.scheduled_job.google_artifact_registry_repository.images" in source
    assert "cost_guard" not in source
    assert "google_storage_bucket" not in source
    assert "terraform_state" not in source
