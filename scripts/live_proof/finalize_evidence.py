"""Complete the sanitized evidence manifest after optional proof steps."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dander.evidence import (
    EVIDENCE_PROOF_NAMES,
    EvidenceBundle,
    EvidenceManifest,
    ProofEvidence,
    utc_now,
)


def _manifest(directory: Path) -> EvidenceManifest:
    path = directory / "manifest.json"
    if path.exists():
        return EvidenceManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
    checked_at = utc_now()
    return EvidenceManifest(
        commit_sha=os.environ.get("GITHUB_SHA", "unknown"),
        workflow_run_id=os.environ.get("GITHUB_RUN_ID", "unknown"),
        checked_at_utc=checked_at,
        gcp_project_alias=os.environ.get("DANDER_GCP_PROJECT_ALIAS", "unknown"),
        container_digest=os.environ.get("DANDER_CONTAINER_DIGEST", "unknown"),
        terraform_plan_sha256=os.environ.get("DANDER_TERRAFORM_PLAN_SHA256", "unknown"),
        proofs={},
    )


def run(evidence_dir: str) -> None:
    directory = Path(evidence_dir)
    manifest = _manifest(directory)
    proofs: dict[str, ProofEvidence] = {}
    for name in EVIDENCE_PROOF_NAMES:
        path = directory / f"{name}.json"
        if path.exists():
            proofs[name] = ProofEvidence.model_validate(
                json.loads(path.read_text(encoding="utf-8"))
            )
    EvidenceBundle(directory).write(manifest.model_copy(update={"proofs": proofs}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", default="evidence")
    args = parser.parse_args()
    run(args.evidence_dir)


if __name__ == "__main__":
    main()
