"""Atomic scaffold for independently distributed connector plugins."""

from __future__ import annotations

import re
import shutil
from importlib import metadata, resources
from pathlib import Path
from tempfile import TemporaryDirectory

from packaging.version import Version

from dander import __version__

_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_DISPLAY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+-]{0,79}$")


class PluginScaffoldError(RuntimeError):
    """Raised when a connector plugin cannot be created without overwriting work."""


def scaffold_connector_plugin(
    plugin_id: str,
    destination: Path,
    *,
    display_name: str | None = None,
) -> Path:
    """Atomically create a generic REST connector-plugin project."""
    if not _PLUGIN_ID.fullmatch(plugin_id):
        raise PluginScaffoldError(
            "Plugin ID must use lowercase letters, numbers, and single underscores"
        )
    resolved_display_name = display_name or plugin_id.replace("_", " ").title()
    if not _DISPLAY_NAME.fullmatch(resolved_display_name):
        raise PluginScaffoldError(
            "Display name must be 1-80 plain letters, numbers, spaces, or ._+- characters"
        )

    requested = destination.expanduser()
    if requested.exists() or requested.is_symlink():
        raise PluginScaffoldError(f"Destination already exists: {requested.absolute()}")
    target = requested.resolve()
    if target.exists() or target.is_symlink():
        raise PluginScaffoldError(f"Destination already exists: {target}")

    distribution_name = f"dander-connector-{plugin_id.replace('_', '-')}"
    package_name = f"dander_connector_{plugin_id}"
    class_name = "".join(part.capitalize() for part in plugin_id.split("_"))
    current = Version(__version__)
    upper = f"{current.major}.{current.minor + 1}"
    replacements = {
        "__PLUGIN_ID__": plugin_id,
        "__DISTRIBUTION_NAME__": distribution_name,
        "__PACKAGE_NAME__": package_name,
        "__SOURCE_CLASS__": f"{class_name}Source",
        "__DISPLAY_NAME__": resolved_display_name,
        "__ENGINE__": f"{plugin_id}_rest",
        "__DANDER_MIN_VERSION__": str(current),
        "__DANDER_MAX_VERSION__": upper,
    }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=f".{target.name}-", dir=target.parent) as temporary:
            staging = Path(temporary) / "plugin"
            template = resources.files("dander").joinpath("templates", "plugin")
            with resources.as_file(template) as template_path:
                shutil.copytree(
                    template_path,
                    staging,
                    ignore=shutil.ignore_patterns(
                        ".mypy_cache",
                        ".pytest_cache",
                        ".ruff_cache",
                        "__pycache__",
                        "*.pyc",
                    ),
                )
            package = staging / "src" / "dander_connector_plugin"
            package.rename(package.with_name(package_name))
            connector = package.with_name(package_name) / "templates" / "plugin.example.yaml"
            connector.rename(connector.with_name(f"{plugin_id}.example.yaml"))
            for path in staging.rglob("*"):
                if path.is_file():
                    content = path.read_text(encoding="utf-8")
                    for placeholder, value in replacements.items():
                        content = content.replace(placeholder, value)
                    path.write_text(content, encoding="utf-8")
            unresolved = [
                path.relative_to(staging)
                for path in staging.rglob("*")
                if path.is_file()
                and any(
                    placeholder in path.read_text(encoding="utf-8") for placeholder in replacements
                )
            ]
            if unresolved:
                raise PluginScaffoldError(
                    f"Connector scaffold has unresolved placeholders: {unresolved}"
                )
            (staging / "LICENSE").write_text(_dander_license(), encoding="utf-8")
            if target.exists() or target.is_symlink():
                raise PluginScaffoldError(f"Destination already exists: {target}")
            staging.rename(target)
    except PluginScaffoldError:
        raise
    except OSError as error:
        raise PluginScaffoldError(f"Could not create connector plugin at {target}") from error
    return target


def _dander_license() -> str:
    distribution = metadata.distribution("dander-platform")
    for relative in distribution.files or ():
        if str(relative).endswith("dist-info/licenses/LICENSE"):
            return Path(str(distribution.locate_file(relative))).read_text(encoding="utf-8")
    source_license = Path(__file__).resolve().parents[3] / "LICENSE"
    if source_license.is_file():
        return source_license.read_text(encoding="utf-8")
    raise PluginScaffoldError("Installed Dander package is missing its Apache-2.0 license")
