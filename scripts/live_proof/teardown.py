"""Record a sanitized retained-resource inventory before any optional teardown decision."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from dander.evidence import ProofEvidence, ProofStatus


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def run(args: argparse.Namespace) -> None:
    started = _now()
    try:
        result = subprocess.run(
            (
                "gcloud",
                "run",
                "jobs",
                "list",
                "--project",
                args.project,
                "--format=json(name)",
            ),
            check=True,
            capture_output=True,
            text=True,
        )
        resources = json.loads(result.stdout)
        count = len(resources) if isinstance(resources, list) else 0
        proof = ProofEvidence(
            status=ProofStatus.PASSED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="retained-resource inventory; no automatic deletion performed",
            row_counts={"cloud_run_jobs": count},
        )
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
        proof = ProofEvidence(
            status=ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="retained-resource inventory; no automatic deletion performed",
            failure_reason="resource inventory failed",
        )
    output = Path(args.evidence_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "teardown.json").write_text(
        json.dumps(proof.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if proof.status is ProofStatus.FAILED:
        raise RuntimeError(proof.failure_reason or "teardown inventory failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--evidence-dir", default="evidence")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
