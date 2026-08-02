"""Stateful, loopback-only Workday RaaS simulator for Dander integration tests.

The simulator models the narrow tenant contract Dander intends to accept first: OAuth token
issuance plus two read-only custom reports. Its records and credentials are entirely invented.
"""

from __future__ import annotations

import argparse
import base64
import json
import socket
from collections import Counter
from contextlib import AbstractContextManager, suppress
from datetime import datetime
from enum import StrEnum
from importlib import resources
from secrets import compare_digest
from threading import Lock, Thread
from time import monotonic, sleep
from typing import Annotated, Any, cast
from urllib.parse import parse_qs

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Path, Query, Request
from pydantic import BaseModel

_CLIENT_ID = "dander-client"
_CLIENT_SECRET = "dander-secret"
_ACCESS_TOKEN = "dander-workday-token"
_EXPECTED_TENANT = "dander-tenant"
_EXPECTED_OWNER = "dander-is"


class WorkdayScenario(StrEnum):
    """Named behaviors exposed through the simulator control API."""

    NORMAL = "normal"
    EXPIRED_CREDENTIALS = "expired_credentials"
    THROTTLING = "throttling"
    MISSING_PERMISSIONS = "missing_permissions"
    MALFORMED_RECORD = "malformed_record"


class ScenarioRequest(BaseModel):
    """Select exactly one deterministic simulator behavior."""

    scenario: WorkdayScenario


class _SimulatorState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._scenario = WorkdayScenario.NORMAL
        self._generation = 0
        self._requests: Counter[str] = Counter()
        self._throttle_consumed = False

    def reset(self) -> None:
        with self._lock:
            self._scenario = WorkdayScenario.NORMAL
            self._generation = 0
            self._requests.clear()
            self._throttle_consumed = False

    def set_scenario(self, scenario: WorkdayScenario) -> None:
        with self._lock:
            self._scenario = scenario
            self._requests.clear()
            self._throttle_consumed = False

    def advance(self) -> int:
        with self._lock:
            self._generation = 1
            return self._generation

    def scenario(self) -> WorkdayScenario:
        with self._lock:
            return self._scenario

    def generation(self) -> int:
        with self._lock:
            return self._generation

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

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "scenario": self._scenario.value,
                "generation": self._generation,
                "requests": dict(self._requests),
            }


def create_workday_simulator() -> FastAPI:
    """Build a fresh simulator app with isolated mutable state."""
    state = _SimulatorState()
    workers_v1 = _load_rows("workers_v1.json")
    workers_v2 = _load_rows("workers_v2.json")
    organizations = _load_rows("organizations.json")
    app = FastAPI(
        title="Dander Workday RaaS simulator",
        version="1.0.0",
        description="Synthetic contract for Dander's first read-only Workday acceptance.",
    )
    app.state.simulator = state

    @app.post(
        "/ccx/oauth2/{tenant}/token",
        operation_id="issueAccessToken",
        tags=["workday-contract"],
    )
    async def issue_access_token(
        request: Request,
        tenant: Annotated[str, Path()],
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, object]:
        _require_tenant(tenant)
        body = parse_qs((await request.body()).decode("utf-8"))
        if body.get("grant_type") != ["client_credentials"]:
            raise HTTPException(status_code=400, detail={"error": "unsupported_grant_type"})
        if state.scenario() is WorkdayScenario.EXPIRED_CREDENTIALS or not _valid_client(
            authorization
        ):
            raise HTTPException(status_code=401, detail={"error": "invalid_client"})
        state.request_number("token")
        return {
            "access_token": _ACCESS_TOKEN,
            "token_type": "Bearer",
            "expires_in": 3600,
        }

    @app.get(
        "/ccx/service/customreport2/{tenant}/{report_owner}/Dander_Workers",
        operation_id="getWorkersReport",
        tags=["workday-contract"],
    )
    def get_workers_report(
        tenant: Annotated[str, Path()],
        report_owner: Annotated[str, Path()],
        authorization: Annotated[str | None, Header()] = None,
        output_format: Annotated[str, Query(alias="format", pattern="^json$")] = "json",
        page: Annotated[int, Query(ge=1)] = 1,
        count: Annotated[int, Query(ge=1, le=100)] = 100,
        updated_after: Annotated[str | None, Query()] = None,
    ) -> dict[str, list[dict[str, object]]]:
        del output_format
        _require_report_access(tenant, report_owner, authorization)
        request_key = f"workers:{page}"
        state.request_number(request_key)
        if state.scenario() is WorkdayScenario.THROTTLING and state.consume_throttle():
            raise HTTPException(
                status_code=429,
                detail={"error": "tenant_throttled"},
                headers={"Retry-After": "0"},
            )
        rows = workers_v2 if state.generation() else workers_v1
        selected = _updated_rows(rows, updated_after)
        if state.scenario() is WorkdayScenario.MALFORMED_RECORD and selected:
            selected[0]["active"] = "not-a-valid-boolean"
        return {"Report_Entry": _page(selected, page=page, count=count)}

    @app.get(
        "/ccx/service/customreport2/{tenant}/{report_owner}/Dander_Organizations",
        operation_id="getOrganizationsReport",
        tags=["workday-contract"],
    )
    def get_organizations_report(
        tenant: Annotated[str, Path()],
        report_owner: Annotated[str, Path()],
        authorization: Annotated[str | None, Header()] = None,
        output_format: Annotated[str, Query(alias="format", pattern="^json$")] = "json",
        page: Annotated[int, Query(ge=1)] = 1,
        count: Annotated[int, Query(ge=1, le=100)] = 100,
        updated_after: Annotated[str | None, Query()] = None,
    ) -> dict[str, list[dict[str, object]]]:
        del output_format
        _require_report_access(tenant, report_owner, authorization)
        state.request_number(f"organizations:{page}")
        if state.scenario() is WorkdayScenario.MISSING_PERMISSIONS:
            raise HTTPException(status_code=403, detail={"error": "insufficient_permissions"})
        selected = _updated_rows(organizations, updated_after)
        return {"Report_Entry": _page(selected, page=page, count=count)}

    @app.put(
        "/_dander/scenario",
        operation_id="setScenario",
        tags=["simulator-control"],
    )
    def set_scenario(request: ScenarioRequest) -> dict[str, str]:
        state.set_scenario(request.scenario)
        return {"scenario": request.scenario.value}

    @app.post(
        "/_dander/advance",
        operation_id="advanceDataset",
        tags=["simulator-control"],
    )
    def advance_dataset() -> dict[str, int]:
        return {"generation": state.advance()}

    @app.post(
        "/_dander/reset",
        operation_id="resetSimulator",
        tags=["simulator-control"],
    )
    def reset_simulator() -> dict[str, str]:
        state.reset()
        return {"status": "reset"}

    return app


def _load_rows(filename: str) -> list[dict[str, object]]:
    fixture = resources.files("dander.dev.fixtures.workday").joinpath(filename)
    payload: Any = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError(f"Invalid packaged Workday fixture: {filename}")
    return [dict(cast("dict[str, object]", row)) for row in payload]


def _require_tenant(tenant: str) -> None:
    if tenant != _EXPECTED_TENANT:
        raise HTTPException(status_code=404, detail={"error": "tenant_not_found"})


def _require_report_access(
    tenant: str,
    report_owner: str,
    authorization: str | None,
) -> None:
    _require_tenant(tenant)
    if report_owner != _EXPECTED_OWNER:
        raise HTTPException(status_code=404, detail={"error": "report_not_found"})
    if authorization != f"Bearer {_ACCESS_TOKEN}":
        raise HTTPException(status_code=401, detail={"error": "expired_access_token"})


def _valid_client(authorization: str | None) -> bool:
    if authorization is None or not authorization.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(authorization.removeprefix("Basic "), validate=True).decode()
    except (UnicodeDecodeError, ValueError):
        return False
    client_id, separator, client_secret = decoded.partition(":")
    return (
        bool(separator)
        and compare_digest(client_id, _CLIENT_ID)
        and compare_digest(client_secret, _CLIENT_SECRET)
    )


def _updated_rows(
    rows: list[dict[str, object]],
    updated_after: str | None,
) -> list[dict[str, object]]:
    copied = [dict(row) for row in rows]
    if updated_after is None:
        return copied
    boundary = _timestamp(updated_after)
    return [row for row in copied if _timestamp(str(row["updated_at"])) > boundary]


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"error": "invalid_updated_after"}) from error
    if parsed.tzinfo is None:
        raise HTTPException(status_code=400, detail={"error": "invalid_updated_after"})
    return parsed


def _page(
    rows: list[dict[str, object]],
    *,
    page: int,
    count: int,
) -> list[dict[str, object]]:
    start = (page - 1) * count
    return rows[start : start + count]


class WorkdaySimulatorServer(AbstractContextManager["WorkdaySimulatorServer"]):
    """Own a background uvicorn service bound to loopback by default."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.app = create_workday_simulator()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((host, port))
        bound_host, bound_port = cast("tuple[str, int]", self._socket.getsockname())
        self._host = bound_host
        self._port = bound_port
        self._server = uvicorn.Server(
            uvicorn.Config(
                self.app,
                log_level="critical",
                access_log=False,
                lifespan="off",
            )
        )
        self._thread: Thread | None = None

    @property
    def base_url(self) -> str:
        """Return the bound base URL, including an ephemeral port when requested."""
        return f"http://{self._host}:{self._port}"

    def start(self) -> WorkdaySimulatorServer:
        """Start serving and wait until uvicorn accepts requests."""
        if self._thread is not None:
            return self
        self._thread = Thread(target=self._serve, name="dander-workday-simulator", daemon=True)
        self._thread.start()
        deadline = monotonic() + 5
        while not self._server.started:
            if not self._thread.is_alive() or monotonic() >= deadline:
                raise RuntimeError("Workday simulator did not start")
            sleep(0.01)
        return self

    def _serve(self) -> None:
        self._server.run(sockets=[self._socket])

    def snapshot(self) -> dict[str, object]:
        """Return sanitized request counters and the active simulator state."""
        state = cast("_SimulatorState", self.app.state.simulator)
        return state.snapshot()

    def wait(self) -> None:
        """Wait for a foreground simulator invocation until interrupted."""
        if self._thread is None:
            raise RuntimeError("Workday simulator is not running")
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

    def __enter__(self) -> WorkdaySimulatorServer:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        del exc_info
        self.close()


def main() -> None:
    """Run the simulator until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    with WorkdaySimulatorServer(args.host, args.port) as server:
        print(f"Dander Workday simulator listening at {server.base_url}", flush=True)
        print("Synthetic credentials: dander-client / dander-secret", flush=True)
        with suppress(KeyboardInterrupt):
            server.wait()


if __name__ == "__main__":
    main()
