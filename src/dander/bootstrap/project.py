"""Batteries-included project bootstrap helpers used by ``dander init``."""

from __future__ import annotations

import hashlib
import re
import subprocess
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_REGION = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
_ACCOUNT = re.compile(r"^[^\s@]+@[^\s@]+$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ProjectBootstrapError(RuntimeError):
    """Raised when the automatic state/image bootstrap cannot complete safely."""


class _Runner(Protocol):
    def __call__(
        self,
        args: tuple[str, ...],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool = False,
        text: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Execute one argument-vector command."""


def _subprocess_runner(
    args: tuple[str, ...],
    *,
    cwd: Path,
    check: bool,
    capture_output: bool = False,
    text: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=capture_output,
        text=text,
    )


class StateBucketBootstrap:
    """Create the one stage-zero GCS backend that Terraform cannot create inside itself."""

    def __init__(self, *, cwd: Path, runner: _Runner | None = None) -> None:
        self._cwd = cwd.resolve()
        self._runner = runner or _subprocess_runner

    def ensure(
        self,
        *,
        project: str,
        bucket: str,
        location: str,
        apply: bool,
    ) -> bool:
        """Ensure a hardened, versioned backend exists; return whether it was created."""
        if not _PROJECT_ID.fullmatch(project):
            raise ProjectBootstrapError("Invalid GCP project id")
        if not _BUCKET_NAME.fullmatch(bucket):
            raise ProjectBootstrapError("Invalid Terraform state bucket")
        described = self._runner(
            (
                "gcloud",
                "storage",
                "buckets",
                "describe",
                f"gs://{bucket}",
                f"--project={project}",
            ),
            cwd=self._cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        if described.returncode == 0:
            return False
        if not apply:
            raise ProjectBootstrapError(
                "The Terraform state bucket does not exist; rerun dander init with --apply"
            )
        try:
            self._runner(
                (
                    "gcloud",
                    "services",
                    "enable",
                    "serviceusage.googleapis.com",
                    "storage.googleapis.com",
                    f"--project={project}",
                    "--quiet",
                ),
                cwd=self._cwd,
                check=True,
            )
            self._runner(
                (
                    "gcloud",
                    "storage",
                    "buckets",
                    "create",
                    f"gs://{bucket}",
                    f"--project={project}",
                    f"--location={location}",
                    "--uniform-bucket-level-access",
                    "--public-access-prevention=enforced",
                    "--labels=managed-by=dander,purpose=terraform-state",
                    "--quiet",
                ),
                cwd=self._cwd,
                check=True,
            )
            self._runner(
                (
                    "gcloud",
                    "storage",
                    "buckets",
                    "update",
                    f"gs://{bucket}",
                    "--versioning",
                    "--quiet",
                ),
                cwd=self._cwd,
                check=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise ProjectBootstrapError("Could not create the Terraform state bucket") from error
        return True


class RuntimeImagePublisher:
    """Build the current Dander project and return its immutable Artifact Registry reference."""

    def __init__(self, repository_dir: Path, *, runner: _Runner | None = None) -> None:
        self._repository_dir = repository_dir.resolve()
        self._runner = runner or _subprocess_runner

    def publish(self, *, project: str, region: str) -> str:
        if not _PROJECT_ID.fullmatch(project) or not _REGION.fullmatch(region):
            raise ProjectBootstrapError("Invalid runtime image project or region")
        host = f"{region}-docker.pkg.dev"
        repository = f"{host}/{project}/dander/dander"
        tag = f"init-{self._content_digest()[:12]}"
        tagged_image = f"{repository}:{tag}"
        try:
            self._runner(
                ("gcloud", "auth", "configure-docker", host, "--quiet"),
                cwd=self._repository_dir,
                check=True,
            )
            self._runner(
                (
                    "docker",
                    "buildx",
                    "build",
                    "--platform",
                    "linux/amd64",
                    "--push",
                    "-t",
                    tagged_image,
                    ".",
                ),
                cwd=self._repository_dir,
                check=True,
            )
            described = self._runner(
                (
                    "gcloud",
                    "artifacts",
                    "docker",
                    "images",
                    "describe",
                    tagged_image,
                    "--format=value(image_summary.digest)",
                ),
                cwd=self._repository_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            raise ProjectBootstrapError("Could not publish the Dander runtime image") from error
        digest = described.stdout.strip()
        if not _DIGEST.fullmatch(digest):
            raise ProjectBootstrapError("Artifact Registry returned an invalid image digest")
        return f"{repository}@{digest}"

    def _content_digest(self) -> str:
        hasher = hashlib.sha256()
        roots = (
            self._repository_dir / "src",
            self._repository_dir / "connectors",
            self._repository_dir / "models",
        )
        files = [
            self._repository_dir / name
            for name in ("Dockerfile", "pyproject.toml", "uv.lock", "dander.yaml")
        ]
        for root in roots:
            files.extend(path for path in root.rglob("*") if path.is_file())
        try:
            for path in sorted(files):
                hasher.update(str(path.relative_to(self._repository_dir)).encode())
                hasher.update(path.read_bytes())
        except OSError as error:
            raise ProjectBootstrapError("Could not hash the runtime build context") from error
        return hasher.hexdigest()


def active_admin_member(*, cwd: Path, runner: _Runner | None = None) -> str:
    """Resolve the active gcloud user as the stage-zero impersonation administrator."""
    command_runner = runner or _subprocess_runner
    try:
        result = command_runner(
            (
                "gcloud",
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
            ),
            cwd=cwd.resolve(),
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ProjectBootstrapError("Could not resolve the active gcloud account") from error
    account = result.stdout.strip()
    if not _ACCOUNT.fullmatch(account):
        raise ProjectBootstrapError("No active gcloud user account was found")
    return f"user:{account}"
