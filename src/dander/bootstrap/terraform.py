"""Safe Terraform planning and explicitly-authorized application."""

from __future__ import annotations

import re
import subprocess
from json import dumps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_STATE_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_REGION = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
_BIGQUERY_LOCATION = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,62}$")
_BILLING_ACCOUNT = re.compile(r"^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$")
_IMMUTABLE_IMAGE = re.compile(r"^[a-z0-9.-]+/[A-Za-z0-9._/-]+@sha256:[0-9a-f]{64}$")
_SECRET_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,254}$")
_GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GITHUB_REF = re.compile(r"^refs/(?:heads|tags)/[A-Za-z0-9._/-]+$")


class TerraformBootstrapError(RuntimeError):
    """Raised when the Terraform bootstrap command cannot complete."""


class TerraformBootstrap:
    """Initialize remote state and produce or apply a saved Terraform plan."""

    def __init__(self, infra_dir: Path) -> None:
        self._infra_dir = infra_dir.resolve()

    def execute(
        self,
        *,
        project: str,
        state_bucket: str,
        state_prefix: str,
        apply: bool,
        region: str = "us-central1",
        bigquery_location: str = "US",
        enable_runtime: bool = False,
        billing_account_id: str = "",
        container_image: str = "",
        scheduler_paused: bool = True,
        secret_ids: tuple[str, ...] = (),
        github_repository: str = "",
        github_ref: str = "refs/heads/main",
    ) -> Path:
        """Create a saved bootstrap plan and optionally apply that exact plan.

        Args:
            project: GCP project id supplied to Terraform.
            state_bucket: Existing GCS bucket used for remote Terraform state.
            state_prefix: Object prefix for the Dander state.
            apply: Whether to apply the saved plan after planning.
            region: GCP region for regional resources.
            bigquery_location: BigQuery dataset location.
            enable_runtime: Whether to provision the scheduled Cloud Run slice.
            billing_account_id: Billing account used by the runtime safety check.
            container_image: Immutable runtime image reference including a sha256 digest.
            scheduler_paused: Whether the scheduler remains paused after provisioning.
            secret_ids: Secret Manager container ids to create without values.
            github_repository: Optional GitHub owner/repository allowed to deploy.
            github_ref: Exact Git branch or tag ref allowed to deploy.

        Returns:
            Path to the saved plan.

        Raises:
            TerraformBootstrapError: If inputs are unsafe, Terraform is unavailable, or a command
                fails.
        """
        for label, value, pattern in (
            ("project", project, _PROJECT_ID),
            ("state bucket", state_bucket, _BUCKET_NAME),
            ("state prefix", state_prefix, _STATE_PREFIX),
            ("region", region, _REGION),
            ("BigQuery location", bigquery_location, _BIGQUERY_LOCATION),
        ):
            if not pattern.fullmatch(value):
                raise TerraformBootstrapError(f"Invalid {label}: {value!r}")

        if enable_runtime:
            if not _BILLING_ACCOUNT.fullmatch(billing_account_id):
                raise TerraformBootstrapError(
                    "Runtime enablement requires --billing-account in XXXXXX-XXXXXX-XXXXXX format"
                )
            if not _IMMUTABLE_IMAGE.fullmatch(container_image):
                raise TerraformBootstrapError(
                    "Runtime enablement requires an immutable --container-image with @sha256 digest"
                )
        elif billing_account_id or container_image:
            raise TerraformBootstrapError(
                "--billing-account and --container-image require --enable-runtime"
            )

        invalid_secrets = sorted(
            {secret_id for secret_id in secret_ids if not _SECRET_ID.fullmatch(secret_id)}
        )
        if invalid_secrets:
            raise TerraformBootstrapError(f"Invalid secret id: {invalid_secrets[0]!r}")
        if github_repository and not _GITHUB_REPOSITORY.fullmatch(github_repository):
            raise TerraformBootstrapError(
                f"Invalid GitHub repository: {github_repository!r}; expected owner/repository"
            )
        if github_repository and not enable_runtime:
            raise TerraformBootstrapError(
                "--github-repository requires --enable-runtime so deployment access has a target"
            )
        if not _GITHUB_REF.fullmatch(github_ref):
            raise TerraformBootstrapError(f"Invalid GitHub ref: {github_ref!r}")

        plan_path = self._infra_dir / "dander-bootstrap.tfplan"
        self._run(
            "terraform",
            "init",
            "-reconfigure",
            f"-backend-config=bucket={state_bucket}",
            f"-backend-config=prefix={state_prefix}",
        )
        self._run(
            "terraform",
            "plan",
            f"-var=project_id={project}",
            f"-var=region={region}",
            f"-var=bigquery_location={bigquery_location}",
            f"-var=enable_scheduled_job={str(enable_runtime).lower()}",
            f"-var=billing_account_id={billing_account_id}",
            f"-var=runtime_container_image={container_image}",
            f"-var=scheduler_paused={str(scheduler_paused).lower()}",
            f"-var=secret_ids={dumps(sorted(set(secret_ids)), separators=(',', ':'))}",
            f"-var=github_repository={github_repository}",
            f"-var=github_ref={github_ref}",
            f"-out={plan_path.name}",
        )
        if apply:
            self._run("terraform", "apply", plan_path.name)
        return plan_path

    def _run(self, *args: str) -> None:
        try:
            subprocess.run(args, cwd=self._infra_dir, check=True)
        except FileNotFoundError as error:
            raise TerraformBootstrapError(
                "Terraform is not installed or is not available on PATH"
            ) from error
        except subprocess.CalledProcessError as error:
            command = " ".join(args[:2])
            raise TerraformBootstrapError(
                f"{command} failed with exit code {error.returncode}"
            ) from error
