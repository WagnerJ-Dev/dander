"""Loopback contract tests for Dander's stateful ServiceNow simulator."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest
import yaml
from dlt.extract.exceptions import ResourceExtractionError
from dlt.sources.helpers.rest_client.paginators import OffsetPaginator

from dander.dev.servicenow_simulator import (
    ServiceNowSimulatorServer,
    create_servicenow_simulator,
)
from dander.ingestion import DltRestSource, OffsetPagination, load_source_config
from dander.runtime import PipelineRunner, RawSchemaError
from dander.security import OAuth2ClientCredentials, OAuthTokenError
from dander.state import SqliteWatermarkStore
from dander.writer import WriteMode, WritePattern, WriteTarget

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

_CONTRACT = Path(__file__).parents[2] / "contracts" / "servicenow-table-simulator.openapi.yaml"
_CONNECTOR = Path(__file__).parents[2] / "connectors" / "servicenow.example.yaml"
_TOKEN_URL = "https://servicenow.example.test/oauth_token.do"
_AUTHORIZATION = {"Authorization": "Bearer dander-servicenow-token"}


class _Secrets:
    def get_secret(self, reference: str) -> str:
        return {
            "servicenow-client-id": "dander-servicenow-client",
            "servicenow-client-secret": "dander-servicenow-secret",
        }[reference]


class _LoopbackTokenRequester:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    def __call__(
        self,
        url: str,
        *,
        auth: tuple[str, str] | None,
        data: Mapping[str, str],
        params: Mapping[str, str],
        headers: Mapping[str, str],
        timeout: float,
    ) -> httpx.Response:
        assert url == _TOKEN_URL
        return httpx.post(
            f"{self._base_url}/oauth_token.do",
            auth=auth,
            data=data,
            params=params,
            headers=headers,
            timeout=timeout,
        )


def _unexpected_token_request(
    url: str,
    *,
    auth: tuple[str, str] | None,
    data: Mapping[str, str],
    params: Mapping[str, str],
    headers: Mapping[str, str],
    timeout: float,
) -> httpx.Response:
    del url, auth, data, params, headers, timeout
    raise AssertionError("credential-free connector rendering must not request a token")


class _CapturingWriter(WritePattern):
    mode = WriteMode.SCD1
    supports_batched_writes = True

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def write(self, records: Iterable[Mapping[str, Any]], target: WriteTarget) -> int:
        assert target.table == "servicenow_incidents"
        batch = [dict(record) for record in records]
        for row in batch:
            self.rows[str(row["sys_id"])] = row
        return len(batch)


@pytest.fixture
def servicenow_server() -> Iterator[ServiceNowSimulatorServer]:
    with ServiceNowSimulatorServer() as server:
        yield server


def _source(
    server: ServiceNowSimulatorServer,
    *,
    page_size: int = 2,
) -> DltRestSource:
    config = load_source_config(_CONNECTOR).model_copy(deep=True)
    config.base_url = f"{server.base_url}/api/now/table"
    config.auth_refs = {
        "client_id": "servicenow-client-id",
        "client_secret": "servicenow-client-secret",
    }
    config.auth_options["token_url"] = _TOKEN_URL
    config.endpoints[0].pagination = OffsetPagination(
        offset_param="sysparm_offset",
        limit_param="sysparm_limit",
        page_size=page_size,
    )
    auth = OAuth2ClientCredentials(
        _Secrets(),
        client_id_ref="servicenow-client-id",
        client_secret_ref="servicenow-client-secret",
        token_url=_TOKEN_URL,
        credential_placement="body",
        request_token=_LoopbackTokenRequester(server.base_url),
    )
    return DltRestSource(config, auth, sleeper=lambda _delay: None)


def _set_scenario(server: ServiceNowSimulatorServer, scenario: str) -> None:
    response = httpx.put(
        f"{server.base_url}/_dander/scenario",
        json={"scenario": scenario},
    )
    response.raise_for_status()


def test_tracked_openapi_contract_matches_fastapi_operations() -> None:
    contract = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8"))
    generated = create_servicenow_simulator().openapi()
    expected = {
        (path, method, operation["operationId"])
        for path, methods in contract["paths"].items()
        for method, operation in methods.items()
        if method != "parameters"
    }
    actual = {
        (path, method, operation["operationId"])
        for path, methods in generated["paths"].items()
        for method, operation in methods.items()
        if method != "parameters" and operation["operationId"] in {item[2] for item in expected}
    }

    assert actual == expected
    assert {operation_id for _, _, operation_id in expected} == {
        "issueAccessToken",
        "listIncidents",
        "createIncident",
        "updateIncident",
        "deleteIncident",
        "setScenario",
        "resetSimulator",
    }


def test_example_connector_is_read_only_stable_and_primitive() -> None:
    config = load_source_config(_CONNECTOR)

    assert config.auth_strategy == "oauth2_client_credentials"
    assert config.auth_options["credential_placement"] == "body"
    endpoint = config.endpoints[0]
    assert endpoint.name == "incidents"
    assert endpoint.incremental_cursor is None
    assert endpoint.primary_key == ["sys_id"]
    assert endpoint.data_selector == "result"
    assert endpoint.query_params == {
        "sysparm_display_value": False,
        "sysparm_exclude_reference_link": True,
        "sysparm_fields": (
            "sys_id,number,short_description,description,state,priority,active,opened_at,"
            "resolved_at,closed_at,sys_created_on,sys_updated_on,sys_updated_by"
        ),
        "sysparm_query": "ORDERBYsys_updated_on^ORDERBYsys_id",
    }
    assert all(field.data_type == "STRING" for field in endpoint.raw_schema)

    rest_config = DltRestSource(
        config,
        OAuth2ClientCredentials(
            _Secrets(),
            client_id_ref="servicenow-client-id",
            client_secret_ref="servicenow-client-secret",
            token_url=_TOKEN_URL,
            credential_placement="body",
            request_token=_unexpected_token_request,
        ),
    ).build_rest_config("incidents")
    resource = rest_config["resources"][0]
    assert isinstance(resource, dict)
    dlt_endpoint = resource["endpoint"]
    assert isinstance(dlt_endpoint, dict)
    assert isinstance(dlt_endpoint["paginator"], OffsetPaginator)
    assert dlt_endpoint["params"] == endpoint.query_params


def test_dander_reads_multiple_pages_and_replays_stateful_updates(
    servicenow_server: ServiceNowSimulatorServer,
) -> None:
    source = _source(servicenow_server)

    initial = list(source.extract("incidents"))
    created_response = httpx.post(
        f"{servicenow_server.base_url}/api/now/table/incident",
        headers=_AUTHORIZATION,
        json={"short_description": "Dander acceptance incident", "priority": "2"},
    )
    created_response.raise_for_status()
    created = created_response.json()["result"]
    update_response = httpx.patch(
        f"{servicenow_server.base_url}/api/now/table/incident/{created['sys_id']}",
        headers=_AUTHORIZATION,
        json={"short_description": "Dander acceptance incident updated", "state": "2"},
    )
    update_response.raise_for_status()

    updated = list(source.extract("incidents"))
    replay = list(source.extract("incidents"))
    delete_response = httpx.delete(
        f"{servicenow_server.base_url}/api/now/table/incident/{created['sys_id']}",
        headers=_AUTHORIZATION,
    )
    delete_response.raise_for_status()

    assert [row["number"] for row in initial] == [
        "INC0010001",
        "INC0010002",
        "INC0010003",
        "INC0010004",
        "INC0010005",
    ]
    assert len(updated) == 6
    updated_proof = next(row for row in updated if row["sys_id"] == created["sys_id"])
    assert updated_proof["short_description"] == "Dander acceptance incident updated"
    assert replay == updated
    snapshot = servicenow_server.snapshot()
    assert snapshot["records"] == 5
    assert cast("dict[str, int]", snapshot["requests"])["incidents:0"] == 3


def test_throttling_retries_the_same_page_once(
    servicenow_server: ServiceNowSimulatorServer,
) -> None:
    _set_scenario(servicenow_server, "throttling")

    rows = list(_source(servicenow_server).extract("incidents"))

    assert len(rows) == 5
    snapshot = servicenow_server.snapshot()
    assert cast("dict[str, int]", snapshot["requests"])["incidents:0"] == 2


def test_expired_credentials_fail_without_exposing_secret(
    servicenow_server: ServiceNowSimulatorServer,
) -> None:
    _set_scenario(servicenow_server, "expired_credentials")

    with pytest.raises(ResourceExtractionError, match="OAuth token request failed") as raised:
        list(_source(servicenow_server).extract("incidents"))

    assert "dander-servicenow-secret" not in str(raised.value)
    assert isinstance(raised.value.__cause__, OAuthTokenError)


def test_missing_permissions_fail_before_rows_are_returned(
    servicenow_server: ServiceNowSimulatorServer,
) -> None:
    _set_scenario(servicenow_server, "missing_permissions")

    with pytest.raises(ResourceExtractionError, match="403"):
        list(_source(servicenow_server).extract("incidents"))


def test_malformed_record_fails_declared_raw_schema(
    servicenow_server: ServiceNowSimulatorServer,
    tmp_path: Path,
) -> None:
    _set_scenario(servicenow_server, "malformed_record")
    runner = PipelineRunner(
        source=_source(servicenow_server, page_size=100),
        writer=_CapturingWriter(),
        watermarks=SqliteWatermarkStore(tmp_path / "state.db"),
        project="synthetic-project",
        dataset="raw",
    )

    with pytest.raises(RawSchemaError, match="Scalar field has a structured value"):
        runner.run()
