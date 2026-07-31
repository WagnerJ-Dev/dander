"""Evidence schema and redaction-topology tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from dander.evidence import EvidenceBundle, EvidenceManifest, ProofEvidence, ProofStatus

if TYPE_CHECKING:
    from pathlib import Path


def test_bundle_writes_manifest_and_all_proofs(tmp_path: Path) -> None:
    manifest = EvidenceManifest(
        commit_sha="a" * 40,
        workflow_run_id="123",
        checked_at_utc="2026-07-31T00:00:00Z",
        gcp_project_alias="proof-project",
        container_digest="sha256:" + "b" * 64,
        terraform_plan_sha256="c" * 64,
        proofs={
            "bootstrap": ProofEvidence(
                status=ProofStatus.PASSED,
                started_at_utc="2026-07-31T00:00:00Z",
                ended_at_utc="2026-07-31T00:01:00Z",
                operation="deployment verification",
                resource_ids=("projects/proof-project",),
                row_counts={"datasets": 3},
                hashes={"plan": "d" * 64},
            )
        },
    )
    EvidenceBundle(tmp_path).write(manifest)

    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "authenticated-ingestion.json").exists()
    assert (
        json.loads((tmp_path / "authenticated-ingestion.json").read_text())["status"] == "skipped"
    )
    assert "secret" not in (tmp_path / "manifest.json").read_text()


def test_evidence_rejects_unknown_fields_and_negative_counts() -> None:
    with pytest.raises(ValueError, match="row_counts"):
        ProofEvidence(
            status=ProofStatus.FAILED,
            started_at_utc="now",
            ended_at_utc="now",
            operation="test",
            row_counts={"rows": -1},
        )
    with pytest.raises(ValueError, match="Unknown proof"):
        EvidenceManifest(
            commit_sha="a" * 40,
            workflow_run_id="123",
            checked_at_utc="now",
            gcp_project_alias="proof",
            container_digest="sha256:" + "b" * 64,
            terraform_plan_sha256="c" * 64,
            proofs={
                "unexpected": ProofEvidence(
                    status=ProofStatus.SKIPPED,
                    started_at_utc="now",
                    ended_at_utc="now",
                    operation="test",
                )
            },
        )
