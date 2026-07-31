"""Publish, read back, and idempotently update one Dataplex aspect."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from dander.catalog import DataplexCatalogPublisher, MetadataSpine
from dander.evidence import ProofEvidence, ProofStatus
from dander.transform import TransformProject


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _hash(value: object) -> str:
    normalized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


def run(args: argparse.Namespace) -> None:
    started = _now()
    try:
        project = TransformProject.load(Path(args.models_dir), project_id=args.project)
        (asset,) = MetadataSpine().compile(project, selected=[args.model])
        publisher = DataplexCatalogPublisher(project=args.project, location=args.location)
        entry_id = publisher.publish(asset)
        first = publisher.normalized_aspects(asset)
        publisher.publish(asset)
        second = publisher.normalized_aspects(asset)
        updated_asset = replace(asset, description=f"{asset.description} Proof metadata update.")
        publisher.publish(updated_asset)
        updated = publisher.normalized_aspects(updated_asset)
        idempotent = _hash(first) == _hash(second)
        changed = _hash(first) != _hash(updated)
        proof = ProofEvidence(
            status=ProofStatus.PASSED if idempotent and changed else ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="Dataplex publish/read-back/idempotence proof",
            resource_ids=(entry_id, f"aspect:{args.model}"),
            hashes={
                "first_read": _hash(first),
                "idempotent_read": _hash(second),
                "updated_read": _hash(updated),
            },
            failure_reason=None
            if idempotent and changed
            else "Dataplex read-back was not idempotent or update was not observed",
        )
    except Exception:  # noqa: BLE001 - preserve only a generic sanitized failure
        proof = ProofEvidence(
            status=ProofStatus.FAILED,
            started_at_utc=started,
            ended_at_utc=_now(),
            operation="Dataplex publish/read-back/idempotence proof",
            resource_ids=(f"aspect:{args.model}",),
            failure_reason="Dataplex proof failed",
        )
    output = Path(args.evidence_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "dataplex.json").write_text(
        json.dumps(proof.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if proof.status is ProofStatus.FAILED:
        raise RuntimeError(proof.failure_reason or "Dataplex proof failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--models-dir", default="models")
    parser.add_argument("--model", default="stg_hubspot__companies")
    parser.add_argument("--location", default="us")
    parser.add_argument("--evidence-dir", default="evidence")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
