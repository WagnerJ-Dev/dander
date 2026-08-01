"""Stage-zero administrative Terraform bootstrap."""

from __future__ import annotations

import os
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
_STAGE_ZERO_STATE_PREFIX = "dander/bootstrap-admin/state"


class AdministrativeBootstrapError(RuntimeError):
    """Raised when stage-zero Terraform cannot safely complete."""


class AdministrativeBootstrap:
    """Create only the state bucket and identity preconditions for platform Terraform."""

    def __init__(self, infra_dir: Path, operator_artifact_dir: Path) -> None:
        self._infra_dir = infra_dir.resolve()
        self._repository_dir = self._infra_dir.parent.parent
        self._operator_artifact_dir = operator_artifact_dir.expanduser().resolve()
        if self._is_within(self._operator_artifact_dir, self._repository_dir):
            raise AdministrativeBootstrapError(
                "Operator artifact directory must be outside the repository checkout"
            )
        self._tf_data_dir = self._operator_artifact_dir / "terraform-data"
        self._plan_path = self._operator_artifact_dir / "dander-admin-bootstrap.tfplan"

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
        adopt_state_bucket: bool = False,
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
            adopt_state_bucket: Import a pre-created stage-zero backend bucket when absent from
                state. Used only by the batteries-included ``dander init`` flow.

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
        self._prepare_operator_directories()
        plan_path = self._plan_path
        self._run(
            "terraform",
            "init",
            "-reconfigure",
            "-input=false",
            f"-backend-config=bucket={state_bucket}",
            f"-backend-config=prefix={_STAGE_ZERO_STATE_PREFIX}",
        )
        if adopt_state_bucket:
            self._adopt_state_bucket(
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
            f"-out={plan_path}",
        )
        try:
            if not plan_path.is_file() or plan_path.is_symlink():
                raise AdministrativeBootstrapError(
                    f"Terraform did not create a regular saved plan at {plan_path}"
                )
            plan_path.chmod(0o600)
        except OSError as error:
            raise AdministrativeBootstrapError(
                f"Could not secure the saved Terraform plan at {plan_path}"
            ) from error
        if apply:
            self._run("terraform", "apply", str(plan_path))
        return plan_path

    @staticmethod
    def _is_within(candidate: Path, parent: Path) -> bool:
        return candidate == parent or parent in candidate.parents

    def _prepare_operator_directories(self) -> None:
        try:
            if self._tf_data_dir.is_symlink():
                raise AdministrativeBootstrapError("terraform-data must not be a symlink")
            if self._tf_data_dir.exists() and not self._tf_data_dir.is_dir():
                raise AdministrativeBootstrapError("terraform-data must be a directory")
            resolved_tf_data_dir = self._tf_data_dir.resolve()
            if not self._is_within(resolved_tf_data_dir, self._operator_artifact_dir):
                raise AdministrativeBootstrapError(
                    "Resolved terraform-data must remain inside the operator artifact directory"
                )
            if self._is_within(resolved_tf_data_dir, self._repository_dir):
                raise AdministrativeBootstrapError(
                    "Resolved terraform-data must remain outside the repository checkout"
                )
            if self._plan_path.is_symlink():
                raise AdministrativeBootstrapError("Saved Terraform plan must not be a symlink")
            if self._plan_path.exists() and not self._plan_path.is_file():
                raise AdministrativeBootstrapError("Saved Terraform plan must be a regular file")
            self._operator_artifact_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._operator_artifact_dir.chmod(0o700)
            self._tf_data_dir.mkdir(mode=0o700, exist_ok=True)
            self._tf_data_dir.chmod(0o700)
            if self._plan_path.exists():
                self._plan_path.chmod(0o600)
                self._plan_path.unlink()
        except OSError as error:
            raise AdministrativeBootstrapError(
                "Could not create or secure the operator artifact directory"
            ) from error

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
        environment = os.environ.copy()
        environment["TF_DATA_DIR"] = str(self._tf_data_dir)
        try:
            subprocess.run(
                args,
                cwd=self._infra_dir,
                env=environment,
                umask=0o077,
                check=True,
            )
        except FileNotFoundError as error:
            raise AdministrativeBootstrapError(
                "Terraform is not installed or is not available on PATH"
            ) from error
        except subprocess.CalledProcessError as error:
            raise AdministrativeBootstrapError(
                f"Terraform command failed with exit code {error.returncode}"
            ) from error

    def _adopt_state_bucket(
        self,
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
        if (
            self._run_status("terraform", "state", "show", "google_storage_bucket.terraform_state")
            == 0
        ):
            return
        self._run(
            "terraform",
            "import",
            f"-var=project_id={project}",
            f"-var=state_bucket={state_bucket}",
            f"-var=admin_member={admin_member}",
            f"-var=region={region}",
            f"-var=state_location={state_location}",
            f"-var=bootstrap_service_account_id={bootstrap_service_account_id}",
            f"-var=billing_account_id={billing_account_id}",
            f"-var=github_repository={github_repository}",
            f"-var=github_ref={github_ref}",
            "google_storage_bucket.terraform_state",
            state_bucket,
        )

    def _run_status(self, *args: str) -> int:
        environment = os.environ.copy()
        environment["TF_DATA_DIR"] = str(self._tf_data_dir)
        try:
            completed = subprocess.run(
                args,
                cwd=self._infra_dir,
                env=environment,
                umask=0o077,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as error:
            raise AdministrativeBootstrapError(
                "Terraform is not installed or is not available on PATH"
            ) from error
        return completed.returncode
