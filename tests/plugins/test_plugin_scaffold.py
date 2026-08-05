"""Generated connector-plugin project safety and completeness."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import pytest
from packaging.version import Version

from dander import __version__
from dander.ingestion import load_source_config
from dander.plugins import PluginScaffoldError, scaffold_connector_plugin

if TYPE_CHECKING:
    from pathlib import Path


def test_scaffold_creates_complete_generic_rest_plugin(tmp_path: Path) -> None:
    target = scaffold_connector_plugin(
        "acme_crm",
        tmp_path / "connector",
        display_name="Acme CRM",
    )

    package = target / "src" / "dander_connector_acme_crm"
    for relative in (
        ".github/workflows/ci.yml",
        ".github/workflows/publish.yml",
        ".gitignore",
        "CHANGELOG.md",
        "HANDOFF.md",
        "LICENSE",
        "README.md",
        "pyproject.toml",
        "src/dander_connector_acme_crm/__init__.py",
        "src/dander_connector_acme_crm/plugin.py",
        "src/dander_connector_acme_crm/source.py",
        "src/dander_connector_acme_crm/templates/acme_crm.example.yaml",
        "tests/test_plugin.py",
    ):
        assert (target / relative).is_file(), relative

    metadata = tomllib.loads((target / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["name"] == "dander-connector-acme-crm"
    current = Version(__version__)
    assert metadata["project"]["dependencies"] == [
        f"dander-platform>={current},<{current.major}.{current.minor + 1}"
    ]
    assert metadata["project"]["entry-points"]["dander.connectors"] == {
        "acme_crm": "dander_connector_acme_crm.plugin:create_plugin"
    }
    assert "uv.lock" in metadata["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    config = load_source_config(package / "templates" / "acme_crm.example.yaml")
    assert config.engine == "acme_crm_rest"
    assert config.auth_strategy == "none"
    assert config.endpoints[0].primary_key == ["id"]
    assert "YOUR-ACCOUNT" in (target / "pyproject.toml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in (target / ".github" / "workflows" / "publish.yml").read_text(
        encoding="utf-8"
    )
    assert "uv sync --frozen --extra dev" in (
        target / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")
    assert not any(
        placeholder in path.read_text(encoding="utf-8")
        for path in target.rglob("*")
        if path.is_file()
        for placeholder in ("__PLUGIN_ID__", "__PACKAGE_NAME__", "__ENGINE__")
    )


def test_scaffold_refuses_to_overwrite_existing_or_linked_paths(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("user work", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.symlink_to(tmp_path / "missing", target_is_directory=True)

    with pytest.raises(PluginScaffoldError, match="already exists"):
        scaffold_connector_plugin("example", existing)
    with pytest.raises(PluginScaffoldError, match="already exists"):
        scaffold_connector_plugin("example", linked)

    assert marker.read_text(encoding="utf-8") == "user work"
    assert linked.is_symlink()


@pytest.mark.parametrize("plugin_id", ["Upper", "two-hyphens", "two__underscores", "9start"])
def test_scaffold_rejects_ambiguous_plugin_ids(tmp_path: Path, plugin_id: str) -> None:
    with pytest.raises(PluginScaffoldError, match="Plugin ID"):
        scaffold_connector_plugin(plugin_id, tmp_path / plugin_id)
