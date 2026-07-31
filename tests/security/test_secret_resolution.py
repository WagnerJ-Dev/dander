"""Security runtime tests for DANDER-20."""

from __future__ import annotations

import logging
from base64 import b64decode
from dataclasses import dataclass
from secrets import token_urlsafe
from typing import TYPE_CHECKING

import httpx
import pytest

from dander.security import (
    ApiKeyBasic,
    DefaultSecretStore,
    EnvironmentSecretStore,
    GcpSecretStore,
    SecretResolutionError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass
class _Payload:
    data: bytes


@dataclass
class _Response:
    payload: _Payload


class _SecretClient:
    def __init__(self, value: str) -> None:
        self.value = value
        self.requests: list[dict[str, str]] = []

    def access_secret_version(self, *, request: Mapping[str, str]) -> _Response:
        self.requests.append(dict(request))
        return _Response(_Payload(self.value.encode()))


def test_environment_secret_access_is_audited_without_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    value = token_urlsafe()
    store = EnvironmentSecretStore({"DANDER_TEST_REFERENCE": value})

    with caplog.at_level(logging.INFO):
        assert store.get_secret("DANDER_TEST_REFERENCE") == value

    assert "credential_access" in caplog.text
    assert "DANDER_TEST_REFERENCE" not in caplog.text
    assert value not in caplog.text
    record = caplog.records[-1]
    assert record.__dict__["credential_actor"] == "dander-runtime"
    assert record.__dict__["secret_backend"] == "environment"
    assert record.__dict__["secret_reference"] == "DANDER_TEST_REFERENCE"


def test_missing_environment_reference_fails_without_exposing_values() -> None:
    store = EnvironmentSecretStore({})
    with pytest.raises(SecretResolutionError, match="missing or empty"):
        store.get_secret("DANDER_TEST_REFERENCE")


def test_default_store_follows_environment_indirection_to_gcp() -> None:
    value = token_urlsafe()
    reference = "projects/unit/secrets/runtime/versions/latest"
    client = _SecretClient(value)
    store = DefaultSecretStore(
        environment=EnvironmentSecretStore({"DANDER_TEST_REFERENCE": reference}),
        gcp=GcpSecretStore(client),
    )

    assert store.get_secret("DANDER_TEST_REFERENCE") == value
    assert client.requests == [{"name": reference}]


def test_api_key_basic_resolves_on_apply() -> None:
    value = token_urlsafe()
    strategy = ApiKeyBasic(
        EnvironmentSecretStore({"DANDER_TEST_REFERENCE": value}),
        "DANDER_TEST_REFERENCE",
    )

    request = strategy.apply(httpx.Request("GET", "https://example.test"))

    assert request.headers["Authorization"].startswith("Basic ")
    encoded = request.headers["Authorization"].removeprefix("Basic ")
    assert b64decode(encoded).decode() == f"{value}:"
