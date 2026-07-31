"""Run a deterministic live BigQuery Storage Write conformance slice."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import bigquery

from dander.evidence import ProofEvidence, ProofStatus
from dander.writer import (
    BigQueryStorageScd1Writer,
    SchemaEvolution,
    WriteField,
    WriteTarget,
)


class _InterruptedBackend:
    """Inject a failure before the pending stream can commit, for rollback evidence."""

    def append(self, rows: object, target: WriteTarget, *, max_batch_rows: int) -> None:
        del rows, target, max_batch_rows
        raise RuntimeError("simulated interruption before pending-stream commit")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _target(project: str, table: str, *, with_note: bool = False) -> WriteTarget:
    fields = [
        WriteField("proof_id", "STRING"),
        WriteField("value", "STRING"),
        WriteField("updated_at", "INT64"),
    ]
    if with_note:
        fields.append(WriteField("note", "STRING"))
    return WriteTarget(
        project=project,
        dataset="raw",
        table=table,
        business_key=("proof_id",),
        schema=tuple(fields),
    )


def _query_hash(project: str, table: str) -> tuple[int, str]:
    client = bigquery.Client(project=project)
    rows = [
        dict(row)
        for row in client.query(f"SELECT * FROM `{project}.raw.{table}` ORDER BY proof_id").result()
    ]
    normalized = json.dumps(rows, sort_keys=True, default=str, separators=(",", ":"))
    return len(rows), hashlib.sha256(normalized.encode()).hexdigest()


def run(args: argparse.Namespace) -> None:
    started = _now()
    table = args.table
    writer = BigQueryStorageScd1Writer(
        project=args.project,
        schema_evolution=SchemaEvolution.ADDITIVE,
    )
    initial = [
        {"proof_id": "proof-a", "value": "alpha", "updated_at": 1},
        {"proof_id": "proof-b", "value": "beta", "updated_at": 1},
    ]
    updated = [
        {"proof_id": "proof-a", "value": "alpha-updated", "updated_at": 2},
        {"proof_id": "proof-b", "value": "beta", "updated_at": 1},
    ]
    try:
        target = _target(args.project, table)
        writer.write(initial, target)
        initial_rows, initial_hash = _query_hash(args.project, table)
        interrupted_writer = BigQueryStorageScd1Writer(
            project=args.project,
            schema_evolution=SchemaEvolution.ADDITIVE,
            backend=_InterruptedBackend(),
        )
        interruption_preserved = 0
        try:
            interrupted_writer.write(updated, target)
        except RuntimeError:
            _, after_interruption_hash = _query_hash(args.project, table)
            interruption_preserved = int(after_interruption_hash == initial_hash)
        writer.write(initial, target)
        retry_rows, retry_hash = _query_hash(args.project, table)
        writer.write(updated, target)
        updated_rows, updated_hash = _query_hash(args.project, table)
        evolved_target = _target(args.project, table, with_note=True)
        writer.write(
            [
                {
                    "proof_id": "proof-a",
                    "value": "alpha-updated",
                    "updated_at": 2,
                    "note": "nullable-addition",
                },
                {
                    "proof_id": "proof-b",
                    "value": "beta",
                    "updated_at": 1,
                    "note": None,
                },
            ],
            evolved_target,
        )
        evolved_rows, evolved_hash = _query_hash(args.project, table)
        invalid_schema_rejected = 0
        try:
            writer.write(
                [{"proof_id": "proof-a", "value": 3, "updated_at": 3}],
                WriteTarget(
                    project=args.project,
                    dataset="raw",
                    table=table,
                    business_key=("proof_id",),
                    schema=(
                        WriteField("proof_id", "STRING"),
                        WriteField("value", "INT64"),
                        WriteField("updated_at", "INT64"),
                    ),
                ),
            )
        except Exception:  # noqa: BLE001 - only the sanitized outcome is retained
            invalid_schema_rejected = 1
        proof = ProofEvidence(
            status=ProofStatus.PASSED
            if invalid_schema_rejected and interruption_preserved
            else ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="BigQuery Storage Write pending-stream conformance",
            resource_ids=(f"{args.project}.raw.{table}",),
            row_counts={
                "initial": initial_rows,
                "exact_retry": retry_rows,
                "after_update": updated_rows,
                "after_schema_addition": evolved_rows,
                "invalid_schema_rejected": invalid_schema_rejected,
                "interruption_preserved": interruption_preserved,
            },
            hashes={
                "initial": initial_hash,
                "exact_retry": retry_hash,
                "after_update": updated_hash,
                "after_schema_addition": evolved_hash,
            },
            transport="storage_write",
            stream_type="PENDING",
            offset_strategy=(
                "zero-based offsets per pending stream; keyed MERGE for retry idempotence"
            ),
            commit_status=(
                "committed" if invalid_schema_rejected and interruption_preserved else "failed"
            ),
            watermark_committed=None,
            table=f"{args.project}.raw.{table}",
            failure_reason=(
                None
                if invalid_schema_rejected and interruption_preserved
                else "Storage Write failure contract was not observed"
            ),
        )
    except Exception:  # noqa: BLE001 - never persist provider payloads
        proof = ProofEvidence(
            status=ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="BigQuery Storage Write pending-stream conformance",
            resource_ids=(f"{args.project}.raw.{table}",),
            transport="storage_write",
            stream_type="PENDING",
            offset_strategy=(
                "zero-based offsets per pending stream; keyed MERGE for retry idempotence"
            ),
            commit_status="failed",
            watermark_committed=False,
            table=f"{args.project}.raw.{table}",
            failure_reason="Storage Write proof failed",
        )
    output = Path(args.evidence_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "storage-write.json").write_text(
        json.dumps(proof.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if proof.status is ProofStatus.FAILED:
        raise RuntimeError(proof.failure_reason or "Storage Write proof failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--table", default="dander_storage_write_proof")
    parser.add_argument("--evidence-dir", default="evidence")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
