"""Safe Terraform planning and explicitly-authorized application."""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_STATE_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


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
    ) -> Path:
        """Create a saved bootstrap plan and optionally apply that exact plan.

        Args:
            project: GCP project id supplied to Terraform.
            state_bucket: Existing GCS bucket used for remote Terraform state.
            state_prefix: Object prefix for the Dander state.
            apply: Whether to apply the saved plan after planning.

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
        ):
            if not pattern.fullmatch(value):
                raise TerraformBootstrapError(f"Invalid {label}: {value!r}")

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
