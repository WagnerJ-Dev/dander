"""Small reusable conformance helpers for connector-plugin authors."""

from __future__ import annotations

from importlib import metadata
from typing import TYPE_CHECKING

from dander.ingestion import Source
from dander.plugins.registry import (
    ENTRY_POINT_GROUP,
    ConnectorPluginError,
    validate_connector_plugin,
)

if TYPE_CHECKING:
    from dander.ingestion import SourceConfig
    from dander.plugins.contracts import ConnectorPlugin
    from dander.security import AuthStrategy


def assert_plugin_conforms(
    factory: object,
    *,
    plugin_id: str,
    source_config: SourceConfig | None = None,
    auth: AuthStrategy | None = None,
) -> ConnectorPlugin:
    """Assert API-v1 structure and, when supplied, the source-factory result.

    ``source_config`` and ``auth`` must be provided together so a partial test cannot
    accidentally appear to validate runtime construction.
    """
    if (source_config is None) != (auth is None):
        raise AssertionError("source_config and auth must be supplied together or both omitted")
    if not callable(factory):
        raise AssertionError("connector plugin entry point must be callable")
    try:
        plugin = validate_connector_plugin(factory(), expected_plugin_id=plugin_id)
    except ConnectorPluginError as error:
        raise AssertionError(str(error)) from error
    if source_config is not None and auth is not None:
        source = plugin.source_factory(source_config, auth)
        if not isinstance(source, Source):
            raise AssertionError(
                f"source factory returned {type(source).__name__}, not dander.ingestion.Source"
            )
    return plugin


def assert_plugin_distribution(
    distribution_name: str,
    *,
    plugin_id: str,
) -> ConnectorPlugin:
    """Assert one installed distribution exposes exactly one matching entry point."""
    try:
        distribution = metadata.distribution(distribution_name)
    except metadata.PackageNotFoundError as error:
        raise AssertionError(
            f"connector distribution is not installed: {distribution_name}"
        ) from error
    entry_points = [
        entry_point
        for entry_point in distribution.entry_points
        if entry_point.group == ENTRY_POINT_GROUP and entry_point.name == plugin_id
    ]
    if len(entry_points) != 1:
        raise AssertionError(
            f"{distribution_name} must expose exactly one {ENTRY_POINT_GROUP} entry point "
            f"named {plugin_id!r}"
        )
    loaded: object = entry_points[0].load()
    return assert_plugin_conforms(loaded, plugin_id=plugin_id)
