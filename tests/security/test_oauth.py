"""OAuth client-credentials tests without external requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from secrets import token_urlsafe
from typing import TYPE_CHECKING

import httpx
import pytest

from dander.security import ClientCredentialPlacement, OAuth2ClientCredentials, OAuthTokenError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from typing import Any


@dataclass
class _Secrets:
    values: dict[str, str]
    accesses: list[str] = field(default_factory=list)

    def get_secret(self, reference: str) -> str:
        self.accesses.append(reference)
        return self.values[reference]


@dataclass
class _TokenServer:
    payloads: list[dict[str, Any]]
    calls: list[dict[str, Any]] = field(default_factory=list)

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
        self.calls.append(
            {
                "url": url,
                "auth": auth,
                "data": dict(data),
                "params": dict(params),
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        payload = self.payloads.pop(0)
        return httpx.Response(
            200,
            json=payload,
            request=httpx.Request("POST", url),
        )


def _strategy(
    server: _TokenServer,
    *,
    clock: Callable[[], float] = lambda: 100.0,
    subject: int | None = None,
    credential_placement: ClientCredentialPlacement = ClientCredentialPlacement.BASIC,
) -> tuple[OAuth2ClientCredentials, _Secrets]:
    secrets = _Secrets({"id_ref": token_urlsafe(), "secret_ref": token_urlsafe()})
    strategy = OAuth2ClientCredentials(
        secrets,
        client_id_ref="id_ref",
        client_secret_ref="secret_ref",
        token_url="https://auth.example.test/token",
        subject=subject,
        credential_placement=credential_placement,
        request_token=server,
        clock=clock,
    )
    return strategy, secrets


def test_oauth_uses_basic_token_exchange_and_caches_bearer() -> None:
    access_token = token_urlsafe()
    server = _TokenServer([{"access_token": access_token, "expires_in": 3600}])
    strategy, secrets = _strategy(server, subject=42)

    first = strategy.apply(httpx.Request("GET", "https://api.example.test/items"))
    second = strategy.apply(httpx.Request("GET", "https://api.example.test/items"))

    assert first.headers["Authorization"] == f"Bearer {access_token}"
    assert second.headers["Authorization"] == f"Bearer {access_token}"
    assert secrets.accesses == ["id_ref", "secret_ref"]
    assert server.calls == [
        {
            "url": "https://auth.example.test/token",
            "auth": (secrets.values["id_ref"], secrets.values["secret_ref"]),
            "data": {"grant_type": "client_credentials", "sub": "42"},
            "params": {},
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
            "timeout": 30.0,
        }
    ]


@pytest.mark.parametrize(
    ("placement", "expected_auth", "expected_data", "expected_params"),
    [
        (
            ClientCredentialPlacement.BODY,
            None,
            {
                "grant_type": "client_credentials",
                "client_id": "CLIENT_ID",
                "client_secret": "CLIENT_SECRET",
            },
            {},
        ),
        (
            ClientCredentialPlacement.QUERY,
            None,
            {},
            {
                "grant_type": "client_credentials",
                "client_id": "CLIENT_ID",
                "client_secret": "CLIENT_SECRET",
            },
        ),
    ],
)
def test_oauth_supports_provider_credential_placement(
    placement: ClientCredentialPlacement,
    expected_auth: tuple[str, str] | None,
    expected_data: dict[str, str],
    expected_params: dict[str, str],
) -> None:
    server = _TokenServer([{"access_token": token_urlsafe(), "expires_in": 3600}])
    strategy, secrets = _strategy(server, credential_placement=placement)
    secrets.values = {"id_ref": "CLIENT_ID", "secret_ref": "CLIENT_SECRET"}

    strategy.apply(httpx.Request("GET", "https://api.example.test"))

    assert server.calls[0]["auth"] == expected_auth
    assert server.calls[0]["data"] == expected_data
    assert server.calls[0]["params"] == expected_params


def test_oauth_refreshes_after_expiry_or_explicit_refresh() -> None:
    now = [100.0]
    access_tokens = [token_urlsafe() for _ in range(3)]
    server = _TokenServer(
        [
            {"access_token": access_tokens[0], "expires_in": 100},
            {"access_token": access_tokens[1], "expires_in": 100},
            {"access_token": access_tokens[2], "expires_in": 100},
        ]
    )
    strategy, _ = _strategy(server, clock=lambda: now[0])

    assert (
        strategy.apply(httpx.Request("GET", "https://api.example.test")).headers["Authorization"]
        == f"Bearer {access_tokens[0]}"
    )
    now[0] = 191.0
    assert (
        strategy.apply(httpx.Request("GET", "https://api.example.test")).headers["Authorization"]
        == f"Bearer {access_tokens[1]}"
    )
    strategy.refresh()
    assert (
        strategy.apply(httpx.Request("GET", "https://api.example.test")).headers["Authorization"]
        == f"Bearer {access_tokens[2]}"
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"access_token": "", "expires_in": 3600},
        {"access_token": token_urlsafe(), "expires_in": "3600"},
        {"access_token": token_urlsafe(), "expires_in": 0},
    ],
)
def test_oauth_rejects_invalid_token_responses(payload: dict[str, Any]) -> None:
    strategy, _ = _strategy(_TokenServer([payload]))

    with pytest.raises(OAuthTokenError):
        strategy.apply(httpx.Request("GET", "https://api.example.test"))


def test_oauth_requires_https_token_endpoint() -> None:
    secrets = _Secrets({})

    with pytest.raises(ValueError, match="HTTPS"):
        OAuth2ClientCredentials(
            secrets,
            client_id_ref="id",
            client_secret_ref="secret",
            token_url="http://auth.example.test/token",
        )


def test_oauth_rejects_unknown_credential_placement() -> None:
    with pytest.raises(ValueError, match="placement"):
        OAuth2ClientCredentials(
            _Secrets({}),
            client_id_ref="id",
            client_secret_ref="secret",
            token_url="https://auth.example.test/token",
            credential_placement="header",
        )
