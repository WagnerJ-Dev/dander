"""Fail-closed sandbox safety tests for DANDER-21."""

from __future__ import annotations

import pytest

from dander.sandbox import GcpBillingVerifier, SandboxDataset, SandboxSafetyError


class _Response:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _Session:
    def __init__(self, response: _Response | Exception) -> None:
        self._response = response

    def get(self, url: str, *, timeout: float) -> _Response:
        assert url.endswith("/projects/unit-project/billingInfo")
        assert timeout == 15.0
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _Verifier:
    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        self._events = events
        self._fail = fail

    def require_disabled(self, project: str) -> None:
        self._events.append(f"verify:{project}")
        if self._fail:
            raise SandboxSafetyError("billing enabled")


class _Client:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def create_dataset(self, dataset: object, *, exists_ok: bool = False) -> object:
        self._events.append(f"create:{dataset}")
        assert exists_ok
        return dataset


def test_billing_verifier_accepts_only_explicit_disabled_response() -> None:
    verifier = GcpBillingVerifier(_Session(_Response(200, {"billingEnabled": False})))

    verifier.require_disabled("unit-project")


@pytest.mark.parametrize(
    "response",
    [
        _Response(200, {"billingEnabled": True}),
        _Response(200, {"billingEnabled": "false"}),
        _Response(200, {}),
        _Response(403, {}),
        RuntimeError("offline"),
    ],
)
def test_billing_verifier_fails_closed(response: _Response | Exception) -> None:
    verifier = GcpBillingVerifier(_Session(response))

    with pytest.raises(SandboxSafetyError):
        verifier.require_disabled("unit-project")


def test_dataset_is_created_only_after_billing_verification() -> None:
    events: list[str] = []
    environment = SandboxDataset(
        verifier=_Verifier(events),
        client=_Client(events),
    )

    environment.prepare("unit-project", "raw")

    assert events[0] == "verify:unit-project"
    assert events[1].startswith("create:")


def test_failed_billing_check_prevents_dataset_creation() -> None:
    events: list[str] = []
    environment = SandboxDataset(
        verifier=_Verifier(events, fail=True),
        client=_Client(events),
    )

    with pytest.raises(SandboxSafetyError, match="billing enabled"):
        environment.prepare("unit-project", "raw")

    assert events == ["verify:unit-project"]
