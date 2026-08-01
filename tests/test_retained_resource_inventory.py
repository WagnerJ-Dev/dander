"""Sanitized retained-resource inventory coverage."""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING

from scripts.live_proof import teardown

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_inventory_retains_only_expected_resource_ids_and_counts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_json(command: tuple[str, ...]) -> object:
        if command[:4] == ("gcloud", "run", "jobs", "list"):
            payload: object = [{"metadata": {"name": "dander-greenhouse-public"}}]
        elif command[:4] == ("gcloud", "scheduler", "jobs", "list"):
            payload = [{"name": "dander-greenhouse-public-daily"}]
        elif command[:4] == ("gcloud", "iam", "service-accounts", "list"):
            payload = [{"email": "dander-runtime@proof-project.iam.gserviceaccount.com"}]
        elif command[:3] == ("gcloud", "secrets", "list"):
            payload = [{"name": "projects/proof-project/secrets/hubspot-private-app-token"}]
        elif command[:4] == ("gcloud", "artifacts", "repositories", "list"):
            payload = [{"name": "projects/proof-project/locations/us/repositories/dander"}]
        elif command[:2] == ("bq", "ls"):
            payload = [
                {"datasetReference": {"datasetId": "raw"}},
                {"datasetReference": {"datasetId": "unrelated"}},
            ]
        else:
            payload = {"name": "proof-state"}
        return json.loads(json.dumps(payload))

    monkeypatch.setattr(teardown, "_json", fake_json)
    output = tmp_path / "evidence"
    teardown.run(
        argparse.Namespace(
            project="proof-project",
            state_bucket="proof-state",
            region="us-central1",
            evidence_dir=str(output),
        )
    )

    evidence = json.loads((output / "teardown.json").read_text(encoding="utf-8"))
    assert evidence["status"] == "passed"
    assert evidence["row_counts"]["cloud_run_jobs"] == 1
    assert evidence["row_counts"]["bigquery_datasets"] == 1
    assert "state_bucket:proof-state" in evidence["resource_ids"]
    assert all("unrelated" not in resource for resource in evidence["resource_ids"])
