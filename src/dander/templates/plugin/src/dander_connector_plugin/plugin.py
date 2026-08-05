"""Dander plugin entry point and presentation-safe connector descriptor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dander.plugins import (
    PLUGIN_API_VERSION,
    ConnectorDescriptor,
    ConnectorEndpointDescriptor,
    ConnectorFieldDescriptor,
    ConnectorPlugin,
)

from __PACKAGE_NAME__.source import __SOURCE_CLASS__

if TYPE_CHECKING:
    from dander.ingestion import Source, SourceConfig
    from dander.security import AuthStrategy


def _source_factory(config: SourceConfig, auth: AuthStrategy) -> Source:
    return __SOURCE_CLASS__(config, auth)


def create_plugin() -> ConnectorPlugin:
    """Return the API-v1 declaration consumed by Dander and Druff."""
    endpoint = ConnectorEndpointDescriptor(
        endpoint_id="records",
        display_name="Records",
        fields=(
            ConnectorFieldDescriptor(
                name="id",
                display_name="ID",
                data_type="STRING",
                required=True,
            ),
        ),
    )
    connector = ConnectorDescriptor(
        connector_id="__PLUGIN_ID__",
        display_name="__DISPLAY_NAME__",
        engine="__ENGINE__",
        description="TODO: describe the verified read-only provider contract.",
        endpoints=(endpoint,),
    )
    return ConnectorPlugin(
        plugin_id="__PLUGIN_ID__",
        api_version=PLUGIN_API_VERSION,
        engine="__ENGINE__",
        display_name="__DISPLAY_NAME__",
        description="TODO: replace this placeholder before publishing.",
        source_factory=_source_factory,
        connectors=(connector,),
    )
