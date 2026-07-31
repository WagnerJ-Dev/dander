"""Stage-zero administrative Terraform bootstrap."""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_REGION = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
_LOCATION = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,62}$")
_BILLING_ACCOUNT = re.compile(r"^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$")
_PRINCIPAL = re.compile(r"^(?:user|serviceAccount|group):[^\r\n]+$")
_SERVICE_ACCOUNT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GITHUB_REF = re.compile(r"^refs/(?:heads|tags)/[A-Za-z0-9._/-]+$")


class AdministrativeBootstrapError(RuntimeError):
    """Raised when stage-zero Terraform cannot safely complete."""


class AdministrativeBootstrap:
    """Create only the state bucket and identity preconditions for platform Terraform."""

    def __init__(self, infra_dir: Path) -> None:
        self._infra_dir = infra_dir.resolve()

    def execute(
        self,
        *,
        project: str,
        state_bucket: str,
        admin_member: str,
        apply: bool,
        region: str = "us-central1",
        state_location: str = "US",
        bootstrap_service_account_id: str = "dander-bootstrap",
        billing_account_id: str = "",
        github_repository: str = "",
        github_ref: str = "refs/heads/main",
    ) -> Path:
        """Plan stage zero and optionally apply that exact saved plan.

        Args:
            project: GCP project receiving the administrative resources.
            state_bucket: Globally unique bucket name for platform Terraform state.
            admin_member: Approved principal allowed to impersonate the bootstrap identity.
            apply: Whether to apply the saved plan after planning.
            region: Provider region.
            state_location: GCS location for the state bucket.
            bootstrap_service_account_id: Account id for the bootstrap service account.
            billing_account_id: Optional billing account for budget-management access.
            github_repository: Optional repository allowed to use proof-workflow WIF.
            github_ref: Exact branch or tag ref allowed to use proof-workflow WIF.

        Returns:
            Path to the saved stage-zero plan.
        """
        self._validate(
            project=project,
            state_bucket=state_bucket,
            admin_member=admin_member,
            region=region,
            state_location=state_location,
            bootstrap_service_account_id=bootstrap_service_account_id,
            billing_account_id=billing_account_id,
            github_repository=github_repository,
            github_ref=github_ref,
        )
        plan_path = self._infra_dir / "dander-admin-bootstrap.tfplan"
        self._run("terraform", "init", "-backend=false", "-input=false")
        self._run(
            "terraform",
            "plan",
            f"-var=project_id={project}",
            f"-var=state_bucket={state_bucket}",
            f"-var=admin_member={admin_member}",
            f"-var=region={region}",
            f"-var=state_location={state_location}",
            f"-var=bootstrap_service_account_id={bootstrap_service_account_id}",
            f"-var=billing_account_id={billing_account_id}",
            f"-var=github_repository={github_repository}",
            f"-var=github_ref={github_ref}",
            f"-out={plan_path.name}",
        )
        if apply:
            self._run("terraform", "apply", plan_path.name)
        return plan_path

    @staticmethod
    def _validate(
        *,
        project: str,
        state_bucket: str,
        admin_member: str,
        region: str,
        state_location: str,
        bootstrap_service_account_id: str,
        billing_account_id: str,
        github_repository: str,
        github_ref: str,
    ) -> None:
        for label, value, pattern in (
            ("project", project, _PROJECT_ID),
            ("state bucket", state_bucket, _BUCKET_NAME),
            ("admin member", admin_member, _PRINCIPAL),
            ("region", region, _REGION),
            ("state location", state_location, _LOCATION),
            ("bootstrap service-account id", bootstrap_service_account_id, _SERVICE_ACCOUNT_ID),
        ):
            if not pattern.fullmatch(value):
                raise AdministrativeBootstrapError(f"Invalid {label}: {value!r}")
        if billing_account_id and not _BILLING_ACCOUNT.fullmatch(billing_account_id):
            raise AdministrativeBootstrapError(
                "Billing account must use XXXXXX-XXXXXX-XXXXXX format"
            )
        if github_repository and not _GITHUB_REPOSITORY.fullmatch(github_repository):
            raise AdministrativeBootstrapError("Invalid GitHub repository")
        if not _GITHUB_REF.fullmatch(github_ref):
            raise AdministrativeBootstrapError("Invalid GitHub ref")

    def _run(self, *args: str) -> None:
        try:
            subprocess.run(args, cwd=self._infra_dir, check=True)
        except FileNotFoundError as error:
            raise AdministrativeBootstrapError(
                "Terraform is not installed or is not available on PATH"
            ) from error
        except subprocess.CalledProcessError as error:
            raise AdministrativeBootstrapError(
                f"Terraform command failed with exit code {error.returncode}"
            ) from error
