"""Batteries-included state and runtime-image bootstrap tests."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from dander.bootstrap import RuntimeImagePublisher, StateBucketBootstrap, active_admin_member

if TYPE_CHECKING:
    from pathlib import Path


class _Runner:
    def __init__(self, *, bucket_exists: bool = False) -> None:
        self.bucket_exists = bucket_exists
        self.commands: list[tuple[str, ...]] = []

    def __call__(
        self,
        args: tuple[str, ...],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool = False,
        text: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd.is_absolute()
        self.commands.append(args)
        if args[:4] == ("gcloud", "storage", "buckets", "describe"):
            return subprocess.CompletedProcess(args, 0 if self.bucket_exists else 1, stdout="")
        if args[:4] == ("gcloud", "artifacts", "docker", "images"):
            return subprocess.CompletedProcess(args, 0, stdout="sha256:" + "a" * 64 + "\n")
        if args[:3] == ("gcloud", "auth", "list"):
            return subprocess.CompletedProcess(args, 0, stdout="operator@example.invalid\n")
        return subprocess.CompletedProcess(args, 0, stdout="")


def test_state_bucket_bootstrap_creates_only_the_hardened_backend(tmp_path: Path) -> None:
    runner = _Runner()

    created = StateBucketBootstrap(cwd=tmp_path, runner=runner).ensure(
        project="unit-project",
        bucket="unit-project-dander-state",
        location="US",
        apply=True,
    )

    assert created
    create = next(command for command in runner.commands if "create" in command)
    assert "--uniform-bucket-level-access" in create
    assert "--public-access-prevention=enforced" in create
    assert any("--versioning" in command for command in runner.commands)


def test_runtime_image_publisher_returns_an_immutable_digest(tmp_path: Path) -> None:
    for name in ("Dockerfile", "pyproject.toml", "uv.lock", "dander.yaml"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    for directory in ("src", "connectors", "models"):
        path = tmp_path / directory
        path.mkdir()
        (path / "content.txt").write_text(directory, encoding="utf-8")
    runner = _Runner()

    image = RuntimeImagePublisher(tmp_path, runner=runner).publish(
        project="unit-project",
        region="us-central1",
    )

    assert image == ("us-central1-docker.pkg.dev/unit-project/dander/dander@sha256:" + "a" * 64)
    build = next(
        command for command in runner.commands if command[:3] == ("docker", "buildx", "build")
    )
    assert "--platform" in build and "linux/amd64" in build and "--push" in build


def test_active_admin_member_uses_the_authenticated_gcloud_user(tmp_path: Path) -> None:
    assert active_admin_member(cwd=tmp_path, runner=_Runner()) == ("user:operator@example.invalid")
