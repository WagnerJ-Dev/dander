"""Record a sanitized retained-resource inventory; never delete cloud resources."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from dander.evidence import ProofEvidence, ProofStatus

_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_REGION = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
_DATASETS = {"raw", "staging", "marts", "dander_meta"}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json(command: tuple[str, ...]) -> object:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _list_ids(payload: object, key: str) -> tuple[str, ...]:
    if not isinstance(payload, list):
        raise ValueError("inventory response was not a list")
    values = []
    for item in payload:
        value: object = item
        for part in key.split("."):
            if not isinstance(value, dict):
                break
            value = value.get(part)
        if not isinstance(value, str):
            raise ValueError("inventory response item had an unexpected shape")
        values.append(value)
    return tuple(values)


def _basename(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


def _inventory(
    project: str, state_bucket: str, region: str
) -> tuple[dict[str, int], tuple[str, ...]]:
    jobs = _list_ids(
        _json(
            (
                "gcloud",
                "run",
                "jobs",
                "list",
                "--project",
                project,
                "--region",
                region,
                "--filter=metadata.labels.owner=dander",
                "--format=json(metadata.name)",
            )
        ),
        "metadata.name",
    )
    schedulers = _list_ids(
        _json(
            (
                "gcloud",
                "scheduler",
                "jobs",
                "list",
                "--project",
                project,
                "--location",
                region,
                "--format=json(name)",
            )
        ),
        "name",
    )
    service_accounts = tuple(
        email
        for email in _list_ids(
            _json(
                (
                    "gcloud",
                    "iam",
                    "service-accounts",
                    "list",
                    "--project",
                    project,
                    "--filter=email:dander-",
                    "--format=json(email)",
                )
            ),
            "email",
        )
        if email.endswith(f"@{project}.iam.gserviceaccount.com")
    )
    secrets = _list_ids(
        _json(
            (
                "gcloud",
                "secrets",
                "list",
                "--project",
                project,
                "--filter=labels.managed-by=dander",
                "--format=json(name)",
            )
        ),
        "name",
    )
    repositories = _list_ids(
        _json(
            (
                "gcloud",
                "artifacts",
                "repositories",
                "list",
                "--project",
                project,
                "--location",
                region,
                "--filter=name~'/dander$'",
                "--format=json(name)",
            )
        ),
        "name",
    )
    dataset_payload = _json(("bq", "ls", f"--project_id={project}", "--format=prettyjson"))
    if not isinstance(dataset_payload, list):
        raise ValueError("dataset inventory response was not a list")
    datasets = tuple(
        item["datasetReference"]["datasetId"]
        for item in dataset_payload
        if isinstance(item, dict)
        and isinstance(item.get("datasetReference"), dict)
        and item["datasetReference"].get("datasetId") in _DATASETS
    )
    bucket = _json(
        (
            "gcloud",
            "storage",
            "buckets",
            "describe",
            f"gs://{state_bucket}",
            "--project",
            project,
            "--format=json(name)",
        )
    )
    if not isinstance(bucket, dict) or _basename(str(bucket.get("name", ""))) != state_bucket:
        raise ValueError("state bucket inventory response did not match")

    counts = {
        "artifact_repositories": len(repositories),
        "bigquery_datasets": len(datasets),
        "cloud_run_jobs": len(jobs),
        "cloud_scheduler_jobs": len(schedulers),
        "secret_containers": len(secrets),
        "service_accounts": len(service_accounts),
        "state_buckets": 1,
    }
    resource_ids = tuple(
        sorted(
            [f"artifact_repository:{_basename(value)}" for value in repositories]
            + [f"bigquery_dataset:{value}" for value in datasets]
            + [f"cloud_run_job:{_basename(value)}" for value in jobs]
            + [f"cloud_scheduler_job:{_basename(value)}" for value in schedulers]
            + [f"secret:{_basename(value)}" for value in secrets]
            + [f"service_account:{value}" for value in service_accounts]
            + [f"state_bucket:{state_bucket}"]
        )
    )
    return counts, resource_ids


def run(args: argparse.Namespace) -> None:
    started = _now()
    try:
        if not _PROJECT.fullmatch(args.project):
            raise ValueError("invalid project id")
        if not _BUCKET.fullmatch(args.state_bucket):
            raise ValueError("invalid state bucket")
        if not _REGION.fullmatch(args.region):
            raise ValueError("invalid region")
        counts, resources = _inventory(args.project, args.state_bucket, args.region)
        proof = ProofEvidence(
            status=ProofStatus.PASSED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="retained-resource inventory; no deletion performed",
            resource_ids=resources,
            row_counts=counts,
        )
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        proof = ProofEvidence(
            status=ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="retained-resource inventory; no deletion performed",
            failure_reason="resource inventory failed",
        )
    output = Path(args.evidence_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "teardown.json").write_text(
        json.dumps(proof.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if proof.status is ProofStatus.FAILED:
        raise RuntimeError(proof.failure_reason or "retained-resource inventory failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--state-bucket", required=True)
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--evidence-dir", default="evidence")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
