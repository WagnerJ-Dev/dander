"""Smoke tests — the package imports and the core value types behave."""

from __future__ import annotations


def test_package_version() -> None:
    import dander

    assert dander.__version__


def test_write_modes_are_distinct() -> None:
    from dander.writer.base import WriteMode

    assert {m.value for m in WriteMode} == {
        "scd1",
        "scd2",
        "snapshot",
        "incremental",
        "replace",
    }


def test_source_config_validates_strategy_specific_auth() -> None:
    import pytest
    from pydantic import ValidationError

    from dander.ingestion.source import SourceConfig

    cfg = SourceConfig(
        name="greenhouse",
        base_url="https://harvest.greenhouse.io/v1",
        auth_strategy="api_key_basic",
        auth_ref="SECRET_GREENHOUSE",
    )
    assert cfg.auth_ref == "SECRET_GREENHOUSE"
    assert cfg.endpoints == []

    public = SourceConfig(
        name="public",
        base_url="https://example.test",
        auth_strategy="none",
    )
    assert public.auth_ref is None

    with pytest.raises(ValidationError, match="client_secret"):
        SourceConfig(
            name="oauth",
            base_url="https://example.test",
            auth_strategy="oauth2_client_credentials",
            auth_refs={"client_id": "CLIENT_ID"},
            auth_options={"token_url": "https://auth.example.test/token"},
        )
