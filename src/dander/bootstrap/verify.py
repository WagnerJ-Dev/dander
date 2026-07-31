"""Read-only verification of resources created by the Terraform bootstrap."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from google.cloud import bigquery


class DeploymentVerificationError(RuntimeError):
    """Raised when the deployment verifier cannot complete its checks."""


@dataclass(frozen=True)
class VerificationCheck:
    """A sanitized check result suitable for a retained evidence artifact."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class DeploymentSummary:
    """Sanitized deployment evidence; it never contains resource payloads."""

    project_id: str
    checked_at_utc: str
    checks: tuple[VerificationCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.ok for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "checked_at_utc": self.checked_at_utc,
            "passed": self.passed,
            "checks": [
                {"name": check.name, "ok": check.ok, "detail": check.detail}
                for check in self.checks
            ],
        }


CommandRunner = Callable[[tuple[str, ...], Path], str]


class DatasetClient(Protocol):
    """Small BigQuery client surface used by the verifier."""

    def get_dataset(self, dataset_ref: str) -> object: ...


BigQueryClientFactory = Callable[[str], DatasetClient]
_IMMUTABLE_IMAGE = re.compile(r"^[a-z0-9.-]+/[A-Za-z0-9._/-]+@sha256:[0-9a-f]{64}$")


def _run_command(args: tuple[str, ...], cwd: Path) -> str:
    """Run a read-only command and return stdout without exposing it to the caller."""
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise DeploymentVerificationError(f"Required command is unavailable: {args[0]}") from error
    except subprocess.CalledProcessError as error:
        raise DeploymentVerificationError(f"Read-only check failed: {args[0]}") from error
    return result.stdout


def _bigquery_client(project: str) -> DatasetClient:
    return bigquery.Client(project=project)


class DeploymentVerifier:
    """Verify actual bootstrap resources using read-only Google Cloud operations."""

    def __init__(
        self,
        *,
        project: str,
        infra_dir: Path = Path("infra"),
        command_runner: CommandRunner = _run_command,
        bigquery_client_factory: BigQueryClientFactory = _bigquery_client,
    ) -> None:
        self.project = project
        self.infra_dir = infra_dir.resolve()
        self._run = command_runner
        self._bigquery_client = bigquery_client_factory

    def verify(
        self,
        *,
        datasets: tuple[str, ...] = ("raw", "staging", "marts"),
        state_bucket: str | None = None,
        state_prefix: str | None = None,
        runtime_job: str | None = None,
        scheduler_job: str | None = None,
        runtime_service_account: str | None = None,
        runtime_image: str | None = None,
        secret_ids: tuple[str, ...] = (),
        region: str = "us-central1",
        expect_cost_guard: bool = False,
        billing_account_id: str | None = None,
    ) -> DeploymentSummary:
        """Return evidence for a deployment; failed checks remain in the summary."""
        checks: list[VerificationCheck] = []
        checks.append(self._check_project())
        checks.extend(self._check_datasets(datasets))
        checks.append(self._check_remote_state(state_bucket, state_prefix))

        if runtime_job is not None:
            runtime_check, discovered_account, discovered_image = self._check_runtime_job(
                runtime_job,
                region,
                runtime_image,
            )
            checks.append(runtime_check)
            runtime_service_account = runtime_service_account or discovered_account
            if runtime_image is None:
                runtime_image = discovered_image
            checks.append(self._check_runtime_iam(runtime_service_account))
        if scheduler_job is not None:
            checks.append(self._check_scheduler(scheduler_job, region))
        checks.extend(self._check_secrets(secret_ids))
        if expect_cost_guard:
            checks.append(self._check_cost_guard(billing_account_id))

        return DeploymentSummary(
            project_id=self.project,
            checked_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            checks=tuple(checks),
        )

    def _check_project(self) -> VerificationCheck:
        try:
            payload = json.loads(
                self._run(
                    ("gcloud", "projects", "describe", self.project, "--format=json"),
                    self.infra_dir,
                )
            )
            ok = (
                payload.get("projectId") == self.project
                and payload.get("lifecycleState") == "ACTIVE"
            )
        except (DeploymentVerificationError, json.JSONDecodeError, AttributeError):
            ok = False
        return VerificationCheck("project", ok, "active" if ok else "unavailable or inactive")

    def _check_datasets(self, datasets: tuple[str, ...]) -> list[VerificationCheck]:
        checks: list[VerificationCheck] = []
        try:
            client = self._bigquery_client(self.project)
        except Exception:  # noqa: BLE001 - evidence must retain a failed check
            return [
                VerificationCheck(f"dataset:{dataset}", False, "unavailable")
                for dataset in datasets
            ]
        for dataset in datasets:
            try:
                client.get_dataset(f"{self.project}.{dataset}")
            except Exception:  # noqa: BLE001 - provider errors must not leak payloads
                checks.append(
                    VerificationCheck(f"dataset:{dataset}", False, "missing or unavailable")
                )
            else:
                checks.append(VerificationCheck(f"dataset:{dataset}", True, "exists"))
        return checks

    def _check_remote_state(
        self,
        state_bucket: str | None,
        state_prefix: str | None,
    ) -> VerificationCheck:
        metadata_path = self.infra_dir / ".terraform" / "terraform.tfstate"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            backend = metadata.get("backend", {})
            config = backend.get("config", {})
            configured = backend.get("type") == "gcs" and bool(config.get("bucket"))
            if state_bucket is not None:
                configured = configured and config.get("bucket") == state_bucket
            if state_prefix is not None:
                configured = configured and config.get("prefix") == state_prefix
            if not configured:
                return VerificationCheck(
                    "remote_state", False, "GCS backend configuration mismatch"
                )
            self._run(("terraform", "state", "pull"), self.infra_dir)
        except (OSError, json.JSONDecodeError, DeploymentVerificationError, AttributeError):
            return VerificationCheck("remote_state", False, "GCS backend unavailable")
        return VerificationCheck("remote_state", True, "GCS backend configured and readable")

    def _check_runtime_job(
        self,
        job_name: str,
        region: str,
        expected_image: str | None,
    ) -> tuple[VerificationCheck, str | None, str | None]:
        try:
            payload = json.loads(
                self._run(
                    (
                        "gcloud",
                        "run",
                        "jobs",
                        "describe",
                        job_name,
                        "--project",
                        self.project,
                        "--region",
                        region,
                        "--format=json",
                    ),
                    self.infra_dir,
                )
            )
            template = payload.get("template", {}).get("template", {})
            containers = template.get("containers", [])
            image = containers[0].get("image") if containers else None
            service_account = template.get("serviceAccount")
            ok = bool(
                image
                and _IMMUTABLE_IMAGE.fullmatch(str(image))
                and service_account
                and (
                    expected_image is None
                    or (_IMMUTABLE_IMAGE.fullmatch(expected_image) and image == expected_image)
                )
            )
            detail = (
                "exists with expected immutable image" if ok else "missing or non-immutable image"
            )
            return VerificationCheck("cloud_run_job", ok, detail), service_account, image
        except (
            DeploymentVerificationError,
            json.JSONDecodeError,
            AttributeError,
            IndexError,
            TypeError,
        ):
            return VerificationCheck("cloud_run_job", False, "missing or unavailable"), None, None

    def _check_runtime_iam(self, service_account: str | None) -> VerificationCheck:
        if not service_account:
            return VerificationCheck("runtime_iam", False, "runtime service account unavailable")
        try:
            payload = json.loads(
                self._run(
                    (
                        "gcloud",
                        "projects",
                        "get-iam-policy",
                        self.project,
                        "--format=json",
                    ),
                    self.infra_dir,
                )
            )
            roles = {
                binding.get("role")
                for binding in payload.get("bindings", [])
                if f"serviceAccount:{service_account}" in binding.get("members", [])
            }
            forbidden = {
                "roles/owner",
                "roles/editor",
                "roles/resourcemanager.projectIamAdmin",
                "roles/iam.serviceAccountAdmin",
                "roles/iam.workloadIdentityPoolAdmin",
                "roles/billing.admin",
            }
            ok = not roles.intersection(forbidden) and "roles/bigquery.jobUser" in roles
            return VerificationCheck(
                "runtime_iam", ok, "narrow project roles" if ok else "broad or incomplete roles"
            )
        except (DeploymentVerificationError, json.JSONDecodeError, AttributeError, TypeError):
            return VerificationCheck("runtime_iam", False, "unavailable")

    def _check_scheduler(self, job_name: str, region: str) -> VerificationCheck:
        try:
            payload = json.loads(
                self._run(
                    (
                        "gcloud",
                        "scheduler",
                        "jobs",
                        "describe",
                        job_name,
                        "--project",
                        self.project,
                        "--location",
                        region,
                        "--format=json",
                    ),
                    self.infra_dir,
                )
            )
            state = str(payload.get("state", "")).upper()
            ok = payload.get("name", "").endswith(f"/jobs/{job_name}") and state in {
                "PAUSED",
                "ENABLED",
            }
            return VerificationCheck(
                "scheduler", ok, f"{state.lower()}" if ok else "missing or unavailable"
            )
        except (DeploymentVerificationError, json.JSONDecodeError, AttributeError, TypeError):
            return VerificationCheck("scheduler", False, "missing or unavailable")

    def _check_secrets(self, secret_ids: tuple[str, ...]) -> list[VerificationCheck]:
        checks: list[VerificationCheck] = []
        for secret_id in secret_ids:
            try:
                payload = json.loads(
                    self._run(
                        (
                            "gcloud",
                            "secrets",
                            "describe",
                            secret_id,
                            "--project",
                            self.project,
                            "--format=json(name)",
                        ),
                        self.infra_dir,
                    )
                )
                ok = payload.get("name", "").endswith(f"/secrets/{secret_id}")
            except (DeploymentVerificationError, json.JSONDecodeError, AttributeError, TypeError):
                ok = False
            checks.append(
                VerificationCheck(
                    f"secret:{secret_id}", ok, "container exists" if ok else "missing"
                )
            )
        return checks

    def _check_cost_guard(self, billing_account_id: str | None) -> VerificationCheck:
        if not billing_account_id:
            return VerificationCheck("cost_guard", False, "billing account is required")
        try:
            payload = json.loads(
                self._run(
                    (
                        "gcloud",
                        "billing",
                        "budgets",
                        "list",
                        "--billing-account",
                        billing_account_id,
                        "--format=json",
                    ),
                    self.infra_dir,
                )
            )
            # The command is intentionally only a connectivity check. Budget names and amounts
            # are not copied into evidence because billing metadata is not needed downstream.
            return VerificationCheck(
                "cost_guard", isinstance(payload, list), "billing metadata readable"
            )
        except (DeploymentVerificationError, json.JSONDecodeError):
            return VerificationCheck("cost_guard", False, "billing metadata unavailable")


def write_summary(summary: DeploymentSummary, output: Path) -> None:
    """Write a sanitized, deterministic JSON summary and create its parent directory."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
