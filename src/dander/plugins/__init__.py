"""Stable connector-plugin API and explicit manifest-driven discovery."""

from dander.plugins.catalog import (
    CATALOG_SCHEMA_VERSION,
    CURATED_CONNECTORS,
    CatalogConnector,
    build_plugin_catalog,
    search_connector_catalog,
)
from dander.plugins.contracts import (
    PLUGIN_API_VERSION,
    ConnectorDescriptor,
    ConnectorEndpointDescriptor,
    ConnectorFieldDescriptor,
    ConnectorPlugin,
    SourceFactory,
)
from dander.plugins.registry import (
    ENTRY_POINT_GROUP,
    ConnectorPluginError,
    ConnectorPluginRegistry,
    InstalledConnectorPlugin,
    load_connector_plugins,
    validate_connector_plugin,
)
from dander.plugins.scaffold import PluginScaffoldError, scaffold_connector_plugin

__all__ = [
    "CATALOG_SCHEMA_VERSION",
    "CURATED_CONNECTORS",
    "PLUGIN_API_VERSION",
    "CatalogConnector",
    "ConnectorDescriptor",
    "ConnectorEndpointDescriptor",
    "ConnectorFieldDescriptor",
    "ConnectorPlugin",
    "ConnectorPluginError",
    "ConnectorPluginRegistry",
    "ENTRY_POINT_GROUP",
    "InstalledConnectorPlugin",
    "PluginScaffoldError",
    "SourceFactory",
    "build_plugin_catalog",
    "load_connector_plugins",
    "scaffold_connector_plugin",
    "search_connector_catalog",
    "validate_connector_plugin",
]
