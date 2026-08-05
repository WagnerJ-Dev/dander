"""Reusable connector-plugin conformance helpers."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import TYPE_CHECKING, Any

import pytest

from dander.ingestion import Source, SourceConfig
from dander.plugins import PLUGIN_API_VERSION, ConnectorPlugin
from dander.plugins.testing import assert_plugin_conforms, assert_plugin_distribution
from dander.security import NoAuth

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class ExampleSource(Source):
    def discover(self) -> Mapping[str, Any]:
        return {}

    def extract(
        self,
        endpoint: str,
        *,
        since: str | None = None,
    ) -> Iterator[Mapping[str, Any]]:
        del endpoint, since
        return iter(())


def create_example_plugin() -> ConnectorPlugin:
    return ConnectorPlugin(
        plugin_id="example",
        api_version=PLUGIN_API_VERSION,
        engine="example_rest",
        display_name="Example",
        source_factory=lambda config, auth: ExampleSource(config),
    )


def test_contract_helper_checks_declaration_and_optional_source_factory() -> None:
    config = SourceConfig(
        name="example",
        engine="example_rest",
        base_url="https://example.test",
        auth_strategy="none",
    )

    declaration = assert_plugin_conforms(create_example_plugin, plugin_id="example")
    constructed = assert_plugin_conforms(
        create_example_plugin,
        plugin_id="example",
        source_config=config,
        auth=NoAuth(),
    )

    assert declaration.engine == constructed.engine == "example_rest"


@pytest.mark.parametrize("with_config", [True, False])
def test_contract_helper_rejects_partial_source_factory_inputs(with_config: bool) -> None:
    config = SourceConfig(
        name="example",
        engine="example_rest",
        base_url="https://example.test",
        auth_strategy="none",
    )

    with pytest.raises(AssertionError, match="must be supplied together"):
        assert_plugin_conforms(
            create_example_plugin,
            plugin_id="example",
            source_config=config if with_config else None,
            auth=None if with_config else NoAuth(),
        )


def test_contract_helper_reports_invalid_factory_and_source_result() -> None:
    with pytest.raises(AssertionError, match="entry point must be callable"):
        assert_plugin_conforms(object(), plugin_id="example")

    invalid = ConnectorPlugin(
        plugin_id="example",
        api_version=PLUGIN_API_VERSION,
        engine="example_rest",
        display_name="Example",
        source_factory=lambda config, auth: object(),  # type: ignore[arg-type,return-value]
    )
    config = SourceConfig(
        name="example",
        engine="example_rest",
        base_url="https://example.test",
        auth_strategy="none",
    )
    with pytest.raises(AssertionError, match="not dander.ingestion.Source"):
        assert_plugin_conforms(
            lambda: invalid,
            plugin_id="example",
            source_config=config,
            auth=NoAuth(),
        )


@dataclass(frozen=True)
class EntryPoint:
    name: str
    group: str = "dander.connectors"

    def load(self) -> object:
        return create_example_plugin


@dataclass(frozen=True)
class Distribution:
    entry_points: tuple[EntryPoint, ...]


def test_distribution_helper_loads_one_matching_entry_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        metadata,
        "distribution",
        lambda name: Distribution((EntryPoint("example"),)),
    )

    plugin = assert_plugin_distribution("dander-connector-example", plugin_id="example")

    assert plugin.engine == "example_rest"
