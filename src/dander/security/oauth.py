"""OAuth 2.0 client-credentials authentication."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from time import monotonic
from typing import TYPE_CHECKING, Any, Protocol

import httpx

from dander.security.base import AuthStrategy

if TYPE_CHECKING:
    from dander.core.interfaces import SecretStoreProvider


class OAuthTokenError(RuntimeError):
    """Raised when an OAuth server does not issue a usable access token."""


class TokenRequester(Protocol):
    """Narrow injectable boundary for the OAuth token request."""

    def __call__(
        self,
        url: str,
        *,
        auth: tuple[str, str],
        data: Mapping[str, str],
        headers: Mapping[str, str],
        timeout: float,
    ) -> httpx.Response:
        """Send one token request."""


class OAuth2ClientCredentials(AuthStrategy):
    """Apply a cached bearer token obtained with OAuth client credentials.

    Client credentials are resolved only when a token is needed. Tokens are refreshed shortly
    before expiry and are never written to connector configuration or logs.
    """

    def __init__(
        self,
        secrets: SecretStoreProvider,
        *,
        client_id_ref: str,
        client_secret_ref: str,
        token_url: str,
        subject: int | None = None,
        request_token: TokenRequester | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        super().__init__(secrets, client_secret_ref)
        if not token_url.startswith("https://"):
            raise ValueError("OAuth token URL must use HTTPS")
        self._client_id_ref = client_id_ref
        self._client_secret_ref = client_secret_ref
        self._token_url = token_url
        self._subject = subject
        self._request_token = request_token or _post_token
        self._clock = clock
        self._access_token: str | None = None
        self._expires_at = 0.0

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Attach a current bearer token to the request."""
        if self._access_token is None or self._clock() >= self._expires_at:
            self._obtain_token()
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        return request

    def refresh(self) -> None:
        """Force the next request to obtain a new token."""
        self._access_token = None
        self._expires_at = 0.0

    def _obtain_token(self) -> None:
        client_id = self._secrets.get_secret(self._client_id_ref)
        client_secret = self._secrets.get_secret(self._client_secret_ref)
        form = {"grant_type": "client_credentials"}
        if self._subject is not None:
            form["sub"] = str(self._subject)

        try:
            response = self._request_token(
                self._token_url,
                auth=(client_id, client_secret),
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OAuthTokenError("OAuth token request failed") from error

        if not isinstance(payload, Mapping):
            raise OAuthTokenError("OAuth token response must be a JSON object")
        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not isinstance(access_token, str) or not access_token:
            raise OAuthTokenError("OAuth token response omitted access_token")
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
            raise OAuthTokenError("OAuth token response omitted numeric expires_in")
        if expires_in <= 0:
            raise OAuthTokenError("OAuth token expiry must be positive")

        self._access_token = access_token
        lifetime = float(expires_in)
        self._expires_at = self._clock() + max(lifetime - 30.0, lifetime * 0.9)


def _post_token(
    url: str,
    *,
    auth: tuple[str, str],
    data: Mapping[str, str],
    headers: Mapping[str, str],
    timeout: float,
) -> httpx.Response:
    """Send a token request through httpx's module-level client."""
    return httpx.post(url, auth=auth, data=data, headers=headers, timeout=timeout)
