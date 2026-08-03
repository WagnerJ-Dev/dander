"""Stateful, loopback-only ServiceNow Table API simulator for integration tests.

The simulator models Dander's first ServiceNow contract: OAuth client credentials and a
read-only, offset-paged incident collection. Mutation routes exist only to prepare acceptance
state; the shipped connector never calls them. All fixtures and credentials are synthetic.
"""

from __future__ import annotations

import argparse
import json
import socket
from collections import Counter
from contextlib import AbstractContextManager, suppress
from datetime import datetime, timedelta
from enum import StrEnum
from importlib import resources
from secrets import compare_digest
from threading import Lock, Thread
from time import monotonic, sleep
from typing import Annotated, Any, cast
from urllib.parse import parse_qs
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel

_CLIENT_ID = "dander-servicenow-client"
_CLIENT_SECRET = "dander-servicenow-secret"
_ACCESS_TOKEN = "dander-servicenow-token"
_ORDER_QUERY = "ORDERBYsys_updated_on^ORDERBYsys_id"


class ServiceNowScenario(StrEnum):
    """Named deterministic behaviors exposed by the simulator control API."""

    NORMAL = "normal"
    EXPIRED_CREDENTIALS = "expired_credentials"
    THROTTLING = "throttling"
    MISSING_PERMISSIONS = "missing_permissions"
    MALFORMED_RECORD = "malformed_record"


class ScenarioRequest(BaseModel):
    """Select one simulator behavior."""

    scenario: ServiceNowScenario


class IncidentCreate(BaseModel):
    """Narrow writable fields used only to prepare simulator acceptance state."""

    short_description: str
    description: str = ""
    state: str = "1"
    priority: str = "4"
    active: str = "true"


class IncidentUpdate(BaseModel):
    """Narrow patch fields used only to advance simulator acceptance state."""

    short_description: str | None = None
    description: str | None = None
    state: str | None = None
    priority: str | None = None
    active: str | None = None


class _SimulatorState:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._lock = Lock()
        self._initial = [dict(row) for row in rows]
        self._rows = {str(row["sys_id"]): dict(row) for row in rows}
        self._scenario = ServiceNowScenario.NORMAL
        self._requests: Counter[str] = Counter()
        self._throttle_consumed = False
        self._clock = datetime(2026, 8, 3, 15, 0, 0)
        self._next_number = 9_000_001

    def reset(self) -> None:
        with self._lock:
            self._rows = {str(row["sys_id"]): dict(row) for row in self._initial}
            self._scenario = ServiceNowScenario.NORMAL
            self._requests.clear()
            self._throttle_consumed = False
            self._clock = datetime(2026, 8, 3, 15, 0, 0)
            self._next_number = 9_000_001

    def set_scenario(self, scenario: ServiceNowScenario) -> None:
        with self._lock:
            self._scenario = scenario
            self._requests.clear()
            self._throttle_consumed = False

    def scenario(self) -> ServiceNowScenario:
        with self._lock:
            return self._scenario

    def request_number(self, key: str) -> int:
        with self._lock:
            self._requests[key] += 1
            return self._requests[key]

    def consume_throttle(self) -> bool:
        with self._lock:
            if self._throttle_consumed:
                return False
            self._throttle_consumed = True
            return True

    def list_rows(self) -> list[dict[str, object]]:
        with self._lock:
            return [dict(row) for row in self._rows.values()]

    def create(self, payload: IncidentCreate) -> dict[str, object]:
        with self._lock:
            timestamp = self._tick()
            sys_id = uuid4().hex
            row: dict[str, object] = {
                "sys_id": sys_id,
                "number": f"INC{self._next_number:07d}",
                "short_description": payload.short_description,
                "description": payload.description,
                "state": payload.state,
                "priority": payload.priority,
                "active": payload.active,
                "opened_at": timestamp,
                "resolved_at": "",
                "closed_at": "",
                "sys_created_on": timestamp,
                "sys_updated_on": timestamp,
                "sys_updated_by": "dander.integration",
            }
            self._next_number += 1
            self._rows[sys_id] = row
            return dict(row)

    def update(self, sys_id: str, payload: IncidentUpdate) -> dict[str, object]:
        with self._lock:
            row = self._rows.get(sys_id)
            if row is None:
                raise HTTPException(status_code=404, detail={"error": "record_not_found"})
            row.update(payload.model_dump(exclude_none=True))
            row["sys_updated_on"] = self._tick()
            row["sys_updated_by"] = "dander.integration"
            return dict(row)

    def delete(self, sys_id: str) -> None:
        with self._lock:
            if self._rows.pop(sys_id, None) is None:
                raise HTTPException(status_code=404, detail={"error": "record_not_found"})

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "scenario": self._scenario.value,
                "records": len(self._rows),
                "requests": dict(self._requests),
            }

    def _tick(self) -> str:
        self._clock += timedelta(seconds=1)
        return self._clock.strftime("%Y-%m-%d %H:%M:%S")


def create_servicenow_simulator() -> FastAPI:
    """Build a fresh simulator app with isolated mutable state."""
    state = _SimulatorState(_load_rows())
    app = FastAPI(
        title="Dander ServiceNow Table API simulator",
        version="1.0.0",
        description="Synthetic contract for Dander's first read-only ServiceNow acceptance.",
    )
    app.state.simulator = state

    @app.post(
        "/oauth_token.do",
        operation_id="issueAccessToken",
        tags=["servicenow-contract"],
    )
    async def issue_access_token(request: Request) -> dict[str, object]:
        body = parse_qs((await request.body()).decode("utf-8"))
        state.request_number("token")
        if (
            state.scenario() is ServiceNowScenario.EXPIRED_CREDENTIALS
            or body.get("grant_type") != ["client_credentials"]
            or not _valid_client(body)
        ):
            raise HTTPException(status_code=401, detail={"error": "invalid_client"})
        return {
            "access_token": _ACCESS_TOKEN,
            "token_type": "Bearer",
            "expires_in": 1800,
        }

    @app.get(
        "/api/now/table/incident",
        operation_id="listIncidents",
        tags=["servicenow-contract"],
    )
    def list_incidents(
        authorization: Annotated[str | None, Header()] = None,
        limit: Annotated[int, Query(alias="sysparm_limit", ge=1, le=10_000)] = 500,
        offset: Annotated[int, Query(alias="sysparm_offset", ge=0)] = 0,
        display_value: Annotated[bool, Query(alias="sysparm_display_value")] = False,
        exclude_reference_link: Annotated[
            bool, Query(alias="sysparm_exclude_reference_link")
        ] = True,
        fields: Annotated[str | None, Query(alias="sysparm_fields")] = None,
        query: Annotated[str, Query(alias="sysparm_query")] = _ORDER_QUERY,
    ) -> dict[str, list[dict[str, object]]]:
        _require_access(authorization)
        state.request_number(f"incidents:{offset}")
        if state.scenario() is ServiceNowScenario.MISSING_PERMISSIONS:
            raise HTTPException(status_code=403, detail={"error": "insufficient_permissions"})
        if state.scenario() is ServiceNowScenario.THROTTLING and state.consume_throttle():
            raise HTTPException(
                status_code=429,
                detail={"error": "rate_limit_exceeded"},
                headers={"Retry-After": "0"},
            )
        if display_value or not exclude_reference_link:
            raise HTTPException(status_code=400, detail={"error": "primitive_values_required"})
        if query != _ORDER_QUERY:
            raise HTTPException(status_code=400, detail={"error": "stable_order_required"})

        rows = sorted(
            state.list_rows(),
            key=lambda row: (str(row["sys_updated_on"]), str(row["sys_id"])),
        )
        selected_fields = fields.split(",") if fields else list(rows[0])
        page = [
            {field: row[field] for field in selected_fields if field in row}
            for row in rows[offset : offset + limit]
        ]
        if state.scenario() is ServiceNowScenario.MALFORMED_RECORD and page:
            page[0]["short_description"] = {"value": "malformed"}
        return {"result": page}

    @app.post(
        "/api/now/table/incident",
        operation_id="createIncident",
        tags=["acceptance-setup"],
    )
    def create_incident(
        payload: IncidentCreate,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, dict[str, object]]:
        _require_access(authorization)
        state.request_number("create")
        return {"result": state.create(payload)}

    @app.patch(
        "/api/now/table/incident/{sys_id}",
        operation_id="updateIncident",
        tags=["acceptance-setup"],
    )
    def update_incident(
        payload: IncidentUpdate,
        sys_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")],
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, dict[str, object]]:
        _require_access(authorization)
        state.request_number("update")
        return {"result": state.update(sys_id, payload)}

    @app.delete(
        "/api/now/table/incident/{sys_id}",
        operation_id="deleteIncident",
        tags=["acceptance-setup"],
        status_code=204,
    )
    def delete_incident(
        sys_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")],
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        _require_access(authorization)
        state.request_number("delete")
        state.delete(sys_id)
        return Response(status_code=204)

    @app.put(
        "/_dander/scenario",
        operation_id="setScenario",
        tags=["simulator-control"],
    )
    def set_scenario(request: ScenarioRequest) -> dict[str, str]:
        state.set_scenario(request.scenario)
        return {"scenario": request.scenario.value}

    @app.post(
        "/_dander/reset",
        operation_id="resetSimulator",
        tags=["simulator-control"],
    )
    def reset_simulator() -> dict[str, str]:
        state.reset()
        return {"status": "reset"}

    return app


def _load_rows() -> list[dict[str, object]]:
    fixture = resources.files("dander.dev.fixtures.servicenow").joinpath("incidents.json")
    payload: Any = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError("Invalid packaged ServiceNow incident fixture")
    return [dict(cast("dict[str, object]", row)) for row in payload]


def _valid_client(body: dict[str, list[str]]) -> bool:
    client_ids = body.get("client_id", [])
    client_secrets = body.get("client_secret", [])
    return (
        len(client_ids) == 1
        and len(client_secrets) == 1
        and compare_digest(client_ids[0], _CLIENT_ID)
        and compare_digest(client_secrets[0], _CLIENT_SECRET)
    )


def _require_access(authorization: str | None) -> None:
    if authorization != f"Bearer {_ACCESS_TOKEN}":
        raise HTTPException(status_code=401, detail={"error": "invalid_token"})


class ServiceNowSimulatorServer(AbstractContextManager["ServiceNowSimulatorServer"]):
    """Own a background simulator service bound to loopback by default."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.app = create_servicenow_simulator()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((host, port))
        bound_host, bound_port = cast("tuple[str, int]", self._socket.getsockname())
        self._host = bound_host
        self._port = bound_port
        self._server = uvicorn.Server(
            uvicorn.Config(self.app, log_level="critical", access_log=False, lifespan="off")
        )
        self._thread: Thread | None = None

    @property
    def base_url(self) -> str:
        """Return the bound loopback URL."""
        return f"http://{self._host}:{self._port}"

    def start(self) -> ServiceNowSimulatorServer:
        """Start serving and wait until uvicorn accepts requests."""
        if self._thread is not None:
            return self
        self._thread = Thread(target=self._serve, name="dander-servicenow-simulator", daemon=True)
        self._thread.start()
        deadline = monotonic() + 5
        while not self._server.started:
            if not self._thread.is_alive() or monotonic() >= deadline:
                raise RuntimeError("ServiceNow simulator did not start")
            sleep(0.01)
        return self

    def _serve(self) -> None:
        self._server.run(sockets=[self._socket])

    def snapshot(self) -> dict[str, object]:
        """Return sanitized request counters and state."""
        state = cast("_SimulatorState", self.app.state.simulator)
        return state.snapshot()

    def wait(self) -> None:
        """Wait for a foreground invocation until interrupted."""
        if self._thread is None:
            raise RuntimeError("ServiceNow simulator is not running")
        while self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def close(self) -> None:
        """Stop the service and release its socket."""
        if self._thread is not None:
            self._server.should_exit = True
            self._thread.join(timeout=5)
            self._thread = None
        if self._socket.fileno() != -1:
            self._socket.close()

    def __enter__(self) -> ServiceNowSimulatorServer:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        del exc_info
        self.close()


def main() -> None:
    """Run the simulator until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    with ServiceNowSimulatorServer(args.host, args.port) as server:
        print(f"Dander ServiceNow simulator listening at {server.base_url}", flush=True)
        print("Synthetic OAuth client: dander-servicenow-client", flush=True)
        with suppress(KeyboardInterrupt):
            server.wait()


if __name__ == "__main__":
    main()
