"""Safe evidence models with an intentionally closed set of retained fields."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from pathlib import Path

EVIDENCE_PROOF_NAMES: Final[tuple[str, ...]] = (
    "bootstrap",
    "authenticated-ingestion",
    "storage-write",
    "transforms",
    "dataplex",
    "iam",
    "cost-guard",
    "teardown",
)
_HEX = "0123456789abcdef"


class ProofStatus(StrEnum):
    """Terminal state retained for one proof operation."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProofEvidence(BaseModel):
    """Sanitized metadata for one proof; payloads and arbitrary fields are forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProofStatus
    started_at_utc: str
    ended_at_utc: str
    operation: str
    resource_ids: tuple[str, ...] = ()
    row_counts: dict[str, int] = Field(default_factory=dict)
    hashes: dict[str, str] = Field(default_factory=dict)
    failure_reason: str | None = None

    @field_validator("row_counts")
    @classmethod
    def _validate_counts(cls, value: dict[str, int]) -> dict[str, int]:
        """Reject negative counts that could make a proof look successful."""
        if any(count < 0 for count in value.values()):
            raise ValueError("row_counts values must be non-negative")
        return value

    @field_validator("hashes")
    @classmethod
    def _validate_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        """Require lowercase hexadecimal digests for stable, non-sensitive hashes."""
        for digest in value.values():
            if not digest or any(character not in _HEX for character in digest):
                raise ValueError("hashes values must be lowercase hexadecimal digests")
        return value


class EvidenceManifest(BaseModel):
    """Manifest tying every proof to its workflow, commit, and immutable image."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    commit_sha: str
    workflow_run_id: str
    checked_at_utc: str
    gcp_project_alias: str
    container_digest: str
    terraform_plan_sha256: str
    proofs: dict[str, ProofEvidence] = Field(default_factory=dict)

    @field_validator("proofs")
    @classmethod
    def _validate_proof_names(cls, value: dict[str, ProofEvidence]) -> dict[str, ProofEvidence]:
        """Keep the artifact topology closed and predictable."""
        unknown = sorted(set(value) - set(EVIDENCE_PROOF_NAMES))
        if unknown:
            raise ValueError(f"Unknown proof name: {unknown[0]}")
        return value


class EvidenceBundle:
    """Write a complete sanitized evidence directory with deterministic JSON formatting."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def write(self, manifest: EvidenceManifest) -> None:
        """Write the manifest and every expected proof file, including skipped proofs."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        for proof_name in EVIDENCE_PROOF_NAMES:
            proof = manifest.proofs.get(proof_name) or ProofEvidence(
                status=ProofStatus.SKIPPED,
                started_at_utc=manifest.checked_at_utc,
                ended_at_utc=manifest.checked_at_utc,
                operation=proof_name,
                failure_reason="proof was not requested",
            )
            self._write_json(self._output_dir / f"{proof_name}.json", proof.model_dump(mode="json"))
        self._write_json(self._output_dir / "manifest.json", manifest.model_dump(mode="json"))

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, separators=(",", ": ")) + "\n",
            encoding="utf-8",
        )


def utc_now() -> str:
    """Return a canonical UTC timestamp for evidence boundaries."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
