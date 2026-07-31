"""Identity proof script tests use only sanitized command results."""

from __future__ import annotations

import json
from argparse import Namespace
from typing import TYPE_CHECKING

import pytest
from scripts.live_proof import identity

if TYPE_CHECKING:
    from pathlib import Path


def test_identity_proof_records_impersonation_and_caller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = iter(
        (
            "dander-bootstrap@proof-project.iam.gserviceaccount.com",
            "dander-bootstrap@proof-project.iam.gserviceaccount.com",
            "github-proof@proof-project.iam.gserviceaccount.com",
        )
    )
    monkeypatch.setattr(identity, "_run", lambda *_args: next(values))

    identity.run(
        Namespace(
            project="proof-project",
            bootstrap_service_account="dander-bootstrap@proof-project.iam.gserviceaccount.com",
            evidence_dir=str(tmp_path),
        )
    )

    proof = json.loads((tmp_path / "iam.json").read_text(encoding="utf-8"))
    assert proof["status"] == "passed"
    assert "caller_type:service_account" in proof["resource_ids"]


def test_identity_proof_fails_closed_on_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        identity,
        "_run",
        lambda *_args: "other@proof-project.iam.gserviceaccount.com",
    )

    with pytest.raises(RuntimeError, match="impersonation"):
        identity.run(
            Namespace(
                project="proof-project",
                bootstrap_service_account="dander-bootstrap@proof-project.iam.gserviceaccount.com",
                evidence_dir=str(tmp_path),
            )
        )
