"""Run the controlled HubSpot companies proof and emit sanitized evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

import httpx
from google.cloud import bigquery

from dander.evidence import ProofEvidence, ProofStatus
from dander.state import BigQueryWatermarkStore

_ID = re.compile(r"^[a-zA-Z0-9_-]+$")
_COMPANY_ID = re.compile(r"^[0-9]+$")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _request(client: httpx.Client, method: str, path: str, **kwargs: object) -> dict[str, object]:
    try:
        response = client.request(method, path, **kwargs)  # type: ignore[arg-type]
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise RuntimeError("HubSpot proof request failed") from error
    if not isinstance(payload, dict):
        raise RuntimeError("HubSpot proof response had an unexpected shape")
    return payload


def _run_job(job: str, region: str) -> None:
    try:
        subprocess.run(
            ("gcloud", "run", "jobs", "execute", job, "--region", region, "--wait"),
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Cloud Run proof job failed") from error


def _snapshot(project: str, table: str, company_ids: tuple[str, ...]) -> tuple[int, str]:
    if not all(_COMPANY_ID.fullmatch(company_id) for company_id in company_ids):
        raise RuntimeError("HubSpot returned an invalid company identifier")
    quoted = ", ".join(f"'{company_id}'" for company_id in company_ids)
    query = (
        f"SELECT company_id, updated_at FROM `{project}.{table}` "
        f"WHERE company_id IN ({quoted}) ORDER BY company_id"
    )
    try:
        rows = [dict(row) for row in bigquery.Client(project=project).query(query).result()]
    except Exception as error:  # noqa: BLE001 - do not expose provider payloads
        raise RuntimeError("HubSpot proof table query failed") from error
    normalized = json.dumps(rows, sort_keys=True, default=str, separators=(",", ":"))
    return len(rows), hashlib.sha256(normalized.encode()).hexdigest()


def _watermark(project: str) -> str | None:
    """Read the committed endpoint cursor without retaining its value in evidence."""
    try:
        return BigQueryWatermarkStore(project=project, dataset="raw").get(
            "hubspot_test", "companies"
        )
    except Exception as error:  # noqa: BLE001 - provider details must stay out of evidence
        raise RuntimeError("HubSpot proof watermark query failed") from error


def _hash_cursor(cursor: str | None) -> str:
    return hashlib.sha256((cursor or "").encode()).hexdigest()


def run(args: argparse.Namespace) -> None:
    started = _now()
    token = os.environ.get(args.token_env)
    if not token:
        raise RuntimeError("HubSpot proof token environment variable is missing")
    properties = {
        "name": f"Dander Proof Company Alpha {args.proof_run_id}",
        "domain": f"dander-proof-alpha-{args.proof_run_id}.invalid",
    }
    ids: list[str] = []
    client = httpx.Client(
        base_url="https://api.hubapi.com",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    try:
        watermark_before = _watermark(args.project)
        for suffix in ("alpha", "beta"):
            created = _request(
                client,
                "POST",
                "/crm/v3/objects/companies",
                json={
                    "properties": {
                        **properties,
                        "name": f"Dander Proof Company {suffix.title()} {args.proof_run_id}",
                        "domain": f"dander-proof-{suffix}-{args.proof_run_id}.invalid",
                    }
                },
            )
            company_id = created.get("id")
            if not isinstance(company_id, str) or not _COMPANY_ID.fullmatch(company_id):
                raise RuntimeError("HubSpot proof create response lacked a valid id")
            ids.append(company_id)
        _run_job(args.job, args.region)
        initial_rows, initial_hash = _snapshot(args.project, args.table, tuple(ids))
        watermark_after_initial = _watermark(args.project)

        _request(
            client,
            "PATCH",
            f"/crm/v3/objects/companies/{ids[0]}",
            json={
                "properties": {"domain": f"dander-proof-alpha-updated-{args.proof_run_id}.invalid"}
            },
        )
        _run_job(args.job, args.region)
        updated_rows, updated_hash = _snapshot(args.project, args.table, tuple(ids))
        watermark_after_update = _watermark(args.project)
        _run_job(args.job, args.region)
        replay_rows, replay_hash = _snapshot(args.project, args.table, tuple(ids))
        watermark_after_replay = _watermark(args.project)
        update_observed = initial_hash != updated_hash
        replay_is_idempotent = (
            updated_hash == replay_hash and watermark_after_update == watermark_after_replay
        )
        watermark_committed = watermark_after_initial is not None and replay_is_idempotent
        proof = ProofEvidence(
            status=ProofStatus.PASSED
            if update_observed and replay_is_idempotent and watermark_committed
            else ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="HubSpot companies initial/update/idempotence proof",
            resource_ids=tuple(ids),
            row_counts={
                "initial": initial_rows,
                "after_update": updated_rows,
                "after_replay": replay_rows,
                "unique_logical_ids": len(set(ids)),
                "update_observed": int(update_observed),
                "watermark_replay_stable": int(watermark_after_update == watermark_after_replay),
            },
            hashes={
                "initial": initial_hash,
                "after_update": updated_hash,
                "after_replay": replay_hash,
                "watermark_before": _hash_cursor(watermark_before),
                "watermark_after_initial": _hash_cursor(watermark_after_initial),
                "watermark_after_update": _hash_cursor(watermark_after_update),
                "watermark_after_replay": _hash_cursor(watermark_after_replay),
            },
            transport="rest",
            commit_status="committed" if watermark_committed else "failed",
            watermark_before_hash=_hash_cursor(watermark_before),
            watermark_after_hash=_hash_cursor(watermark_after_replay),
            watermark_committed=watermark_committed,
            table=f"{args.project}.{args.table}",
            failure_reason=None
            if update_observed and replay_is_idempotent and watermark_committed
            else "HubSpot update, idempotence, or watermark contract failed",
        )
    except Exception as error:  # noqa: BLE001 - evidence must retain failure without payloads
        proof = ProofEvidence(
            status=ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="HubSpot companies initial/update/idempotence proof",
            resource_ids=tuple(ids),
            transport="rest",
            commit_status="failed",
            watermark_committed=False,
            table=f"{args.project}.{args.table}",
            failure_reason=str(error),
        )
        _write(args.evidence_dir, proof)
        raise
    finally:
        for company_id in ids:
            with suppress(httpx.HTTPError):
                client.delete(f"/crm/v3/objects/companies/{company_id}")
        client.close()
    _write(args.evidence_dir, proof)


def _write(directory: str, proof: ProofEvidence) -> None:
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    (output / "authenticated-ingestion.json").write_text(
        json.dumps(proof.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--table", default="staging.stg_hubspot__companies")
    parser.add_argument("--job", default="dander-greenhouse-public")
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--proof-run-id", required=True)
    parser.add_argument("--token-env", default="HUBSPOT_PRIVATE_APP_TOKEN")
    parser.add_argument("--evidence-dir", default="evidence")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
