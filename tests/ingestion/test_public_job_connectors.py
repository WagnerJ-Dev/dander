"""Offline contracts for credential-free public ATS connectors."""

from __future__ import annotations

from pathlib import Path

import pytest
from dlt.sources.helpers.rest_client.paginators import (
    JSONResponseCursorPaginator,
    OffsetPaginator,
    SinglePagePaginator,
)
from pydantic import ValidationError

from dander.ingestion import DltRestSource, Endpoint, load_source_config
from dander.security import ApiKeyBearer, NoAuth

_CONNECTORS = Path(__file__).parents[2] / "connectors"


def test_lever_connector_maps_public_json_and_offset_pagination() -> None:
    config = load_source_config(_CONNECTORS / "lever_job_board.yaml")

    assert config.auth_strategy == "none"
    rest_config = DltRestSource(config, NoAuth()).build_rest_config("jobs")
    assert rest_config["client"]["base_url"] == "https://api.lever.co/v0/postings/"
    resource = rest_config["resources"][0]
    assert isinstance(resource, dict)
    assert resource["primary_key"] == ["id"]
    endpoint = resource["endpoint"]
    assert isinstance(endpoint, dict)
    assert endpoint["path"] == "spotify"
    assert endpoint["params"] == {"mode": "json"}
    assert isinstance(endpoint["paginator"], OffsetPaginator)


def test_ashby_connector_maps_public_envelope_and_compensation_flag() -> None:
    config = load_source_config(_CONNECTORS / "ashby_job_board.yaml")

    assert config.auth_strategy == "none"
    rest_config = DltRestSource(config, NoAuth()).build_rest_config("jobs")
    resource = rest_config["resources"][0]
    assert isinstance(resource, dict)
    endpoint = resource["endpoint"]
    assert isinstance(endpoint, dict)
    assert endpoint["path"] == "Ashby"
    assert endpoint["data_selector"] == "jobs"
    assert endpoint["params"] == {"includeCompensation": True}
    assert isinstance(endpoint["paginator"], SinglePagePaginator)


def test_hubspot_connector_maps_bearer_auth_and_cursor_pagination() -> None:
    config = load_source_config(_CONNECTORS / "hubspot_test.yaml")

    assert config.auth_strategy == "api_key_bearer"
    rest_config = DltRestSource(
        config, ApiKeyBearer(SecretStore(), config.auth_ref or "")
    ).build_rest_config("companies")
    resource = rest_config["resources"][0]
    assert isinstance(resource, dict)
    endpoint = resource["endpoint"]
    assert isinstance(endpoint, dict)
    assert endpoint["path"] == "crm/v3/objects/companies"
    assert endpoint["params"] == {
        "archived": False,
        "limit": 100,
        "properties": "name,domain,createdate,lastmodifieddate",
    }
    assert endpoint["data_selector"] == "results"
    assert isinstance(endpoint["paginator"], JSONResponseCursorPaginator)


class SecretStore:
    def get_secret(self, reference: str) -> str:
        assert reference == "HUBSPOT_PRIVATE_APP_TOKEN"
        return "unit-secret"


@pytest.mark.parametrize("name", ["api_key", "access_token", "client-secret", "password"])
def test_static_query_params_reject_credential_like_names(name: str) -> None:
    with pytest.raises(ValidationError, match="use auth_strategy"):
        Endpoint(
            name="jobs",
            path="/jobs",
            query_params={name: "not-a-real-secret"},
        )
