"""Verify hosted transform output without retaining source rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import bigquery

from dander.evidence import ProofEvidence, ProofStatus


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run_job(job: str, region: str) -> None:
    try:
        subprocess.run(
            ("gcloud", "run", "jobs", "execute", job, "--region", region, "--wait"),
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Cloud Run transform proof job failed") from error


def _snapshot(project: str, dataset: str, table: str) -> tuple[int, str]:
    client = bigquery.Client(project=project)
    query = (
        f"SELECT COUNT(*) AS row_count, COUNT(DISTINCT TO_JSON_STRING(t)) AS distinct_rows "
        f"FROM `{project}.{dataset}.{table}` AS t"
    )
    try:
        row = next(iter(client.query(query).result()))
    except Exception as error:  # noqa: BLE001 - retain only a sanitized failure
        raise RuntimeError("Hosted transform table query failed") from error
    count = int(row["row_count"])
    distinct = int(row["distinct_rows"])
    digest = hashlib.sha256(f"{count}:{distinct}".encode()).hexdigest()
    return count, digest


def run(args: argparse.Namespace) -> None:
    started = _now()
    resource = f"{args.project}.{args.dataset}.{args.table}"
    try:
        _run_job(args.job, args.region)
        first_count, first_hash = _snapshot(args.project, args.dataset, args.table)
        _run_job(args.job, args.region)
        replay_count, replay_hash = _snapshot(args.project, args.dataset, args.table)
        proof = ProofEvidence(
            status=ProofStatus.PASSED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="Hosted transform build/test and replay proof",
            resource_ids=(resource,),
            row_counts={"first_run": first_count, "replay": replay_count},
            hashes={"first_run": first_hash, "replay": replay_hash},
        )
    except Exception:  # noqa: BLE001 - never persist provider payloads
        proof = ProofEvidence(
            status=ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="Hosted transform build/test and replay proof",
            resource_ids=(resource,),
            failure_reason="Hosted transform proof failed",
        )
    output = Path(args.evidence_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "transforms.json").write_text(
        json.dumps(proof.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if proof.status is ProofStatus.FAILED:
        raise RuntimeError(proof.failure_reason or "Hosted transform proof failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="staging")
    parser.add_argument("--table", default="stg_greenhouse__jobs")
    parser.add_argument("--job", default="dander-greenhouse-public")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--evidence-dir", default="evidence")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
