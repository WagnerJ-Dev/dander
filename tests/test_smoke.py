"""Smoke tests — the package imports and the core value types behave."""

from __future__ import annotations


def test_package_version() -> None:
    import dander

    assert dander.__version__


def test_write_modes_are_distinct() -> None:
    from dander.writer.base import WriteMode

    assert {m.value for m in WriteMode} == {"scd1", "scd2", "snapshot", "incremental"}


def test_source_config_requires_auth_ref() -> None:
    from dander.ingestion.source import SourceConfig

    cfg = SourceConfig(
        name="greenhouse",
        base_url="https://harvest.greenhouse.io/v1",
        auth_strategy="api_key_basic",
        auth_ref="SECRET_GREENHOUSE",
    )
    assert cfg.auth_ref == "SECRET_GREENHOUSE"
    assert cfg.endpoints == []
