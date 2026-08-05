"""Generated plugin contract smoke tests."""

from pathlib import Path

from dander.ingestion import load_source_config
from dander.plugins.testing import assert_plugin_conforms, assert_plugin_distribution
from dander.security import NoAuth

from __PACKAGE_NAME__ import __SOURCE_CLASS__, create_plugin


def test_plugin_contract_distribution_and_source_factory() -> None:
    config = load_source_config(
        Path(__file__).parents[1]
        / "src"
        / "__PACKAGE_NAME__"
        / "templates"
        / "__PLUGIN_ID__.example.yaml"
    )

    plugin = assert_plugin_conforms(
        create_plugin,
        plugin_id="__PLUGIN_ID__",
        source_config=config,
        auth=NoAuth(),
    )
    installed = assert_plugin_distribution(
        "__DISTRIBUTION_NAME__",
        plugin_id="__PLUGIN_ID__",
    )

    assert plugin.engine == "__ENGINE__"
    assert installed.engine == plugin.engine
    assert isinstance(plugin.source_factory(config, NoAuth()), __SOURCE_CLASS__)
