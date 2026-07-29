"""dlt REST adapter tests for DANDER-20."""

from __future__ import annotations

from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any

from dlt.sources.helpers.rest_client.auth import AuthConfigBase
from dlt.sources.helpers.rest_client.paginators import HeaderLinkPaginator
from requests import Request

from dander.ingestion.dlt_backed import DltAuthAdapter, DltRestSource
from dander.ingestion.source import Endpoint, SourceConfig
from dander.security import NoAuth
from dander.security.base import AuthStrategy

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    import httpx
    import pytest


class _Auth(AuthStrategy):
    def __init__(self, secrets: _Secrets, auth_ref: str) -> None:
        super().__init__(secrets, auth_ref)
        self.header = f"Basic {token_urlsafe()}"

    def apply(self, request: httpx.Request) -> httpx.Request:
        request.headers["Authorization"] = self.header
        return request


class _Secrets:
    def get_secret(self, reference: str) -> str:
        raise AssertionError(reference)


def _config() -> SourceConfig:
    return SourceConfig(
        name="example",
        base_url="https://example.test/v1",
        auth_strategy="api_key_basic",
        auth_ref="DANDER_TEST_REFERENCE",
        endpoints=[
            Endpoint(
                name="widgets",
                path="/widgets",
                pagination="link_header",
                incremental_cursor="updated_at",
                cursor_param="updated_after",
                primary_key=["id"],
            )
        ],
    )


def test_build_config_maps_auth_pagination_cursor_and_key() -> None:
    auth = _Auth(_Secrets(), "DANDER_TEST_REFERENCE")
    source = DltRestSource(_config(), auth)

    config = source.build_rest_config("widgets", since="2026-01-01T00:00:00Z")

    assert config["client"]["base_url"] == "https://example.test/v1/"
    adapter = config["client"]["auth"]
    assert isinstance(adapter, DltAuthAdapter)
    assert isinstance(adapter, AuthConfigBase)
    prepared = Request("GET", "https://example.test/v1/widgets").prepare()
    assert adapter(prepared).headers["Authorization"] == auth.header
    resource = config["resources"][0]
    assert isinstance(resource, dict)
    assert resource["primary_key"] == ["id"]
    endpoint = resource["endpoint"]
    assert isinstance(endpoint, dict)
    assert isinstance(endpoint["paginator"], HeaderLinkPaginator)
    assert endpoint["params"] == {"updated_after": "2026-01-01T00:00:00Z"}


def test_build_config_supports_public_enveloped_response() -> None:
    config = SourceConfig(
        name="public",
        base_url="https://example.test/v1/boards",
        auth_strategy="none",
        endpoints=[
            Endpoint(
                name="jobs",
                path="/demo/jobs",
                data_selector="jobs",
                primary_key=["id"],
            )
        ],
    )

    rest_config = DltRestSource(config, NoAuth()).build_rest_config("jobs")

    resource = rest_config["resources"][0]
    assert isinstance(resource, dict)
    endpoint = resource["endpoint"]
    assert isinstance(endpoint, dict)
    assert endpoint["data_selector"] == "jobs"
    adapter = rest_config["client"]["auth"]
    assert isinstance(adapter, DltAuthAdapter)
    prepared = Request("GET", "https://example.test/v1/boards/demo/jobs").prepare()
    assert "Authorization" not in adapter(prepared).headers


class _FakeDltSource:
    def with_resources(self, *resource_names: str) -> _FakeDltSource:
        assert resource_names == ("widgets",)
        return self

    def __iter__(self) -> Iterator[Mapping[str, Any]]:
        yield {"id": "synthetic"}


def test_extract_yields_mapping_items(monkeypatch: pytest.MonkeyPatch) -> None:
    source = DltRestSource(_config(), _Auth(_Secrets(), "DANDER_TEST_REFERENCE"))

    def fake_rest_api_source(config: object, name: str) -> _FakeDltSource:
        assert config
        assert name == "example"
        return _FakeDltSource()

    monkeypatch.setattr("dander.ingestion.dlt_backed.rest_api_source", fake_rest_api_source)

    assert list(source.extract("widgets")) == [{"id": "synthetic"}]
