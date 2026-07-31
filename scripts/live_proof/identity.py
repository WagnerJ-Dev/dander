"""Verify the configured WIF caller and bootstrap impersonation boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from dander.evidence import ProofEvidence, ProofStatus


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run(*args: str) -> str:
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise RuntimeError("identity verification command failed") from error
    return result.stdout.strip()


def run(args: argparse.Namespace) -> None:
    started = _now()
    resource_ids = (args.bootstrap_service_account,)
    try:
        impersonated = _run("gcloud", "config", "get-value", "auth/impersonate_service_account")
        described = _run(
            "gcloud",
            "iam",
            "service-accounts",
            "describe",
            args.bootstrap_service_account,
            "--project",
            args.project,
            "--format=value(email)",
        )
        caller = _run(
            "gcloud",
            "auth",
            "list",
            "--filter=status:ACTIVE",
            "--format=value(account)",
        )
        caller_type = (
            "service_account"
            if caller.endswith(".iam.gserviceaccount.com")
            else "external_identity"
        )
        passed = (
            impersonated == args.bootstrap_service_account
            and described == args.bootstrap_service_account
        )
        proof = ProofEvidence(
            status=ProofStatus.PASSED if passed else ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="WIF caller and bootstrap service-account impersonation verification",
            resource_ids=resource_ids + (f"caller_type:{caller_type}",),
            hashes={},
            failure_reason=None
            if passed
            else "configured impersonation did not match bootstrap identity",
        )
    except Exception:  # noqa: BLE001 - retain only a sanitized failure
        proof = ProofEvidence(
            status=ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="WIF caller and bootstrap service-account impersonation verification",
            resource_ids=resource_ids,
            failure_reason="identity verification failed",
        )
    output = Path(args.evidence_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "iam.json").write_text(
        json.dumps(proof.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if proof.status is ProofStatus.FAILED:
        raise RuntimeError(proof.failure_reason or "identity verification failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--bootstrap-service-account", required=True)
    parser.add_argument("--evidence-dir", default="evidence")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
