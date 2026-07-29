"""API-key authentication strategies."""

from __future__ import annotations

from base64 import b64encode
from typing import TYPE_CHECKING

from dander.security.base import AuthStrategy

if TYPE_CHECKING:
    import httpx


class ApiKeyBasic(AuthStrategy):
    """Apply an API key as the username of an HTTP Basic credential.

    Legacy Greenhouse Harvest v1 uses the API key as the username and an empty password. The
    secret is resolved for each request so no long-lived credential value is stored on the
    strategy.
    """

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Attach the Basic authorization header to `request`."""
        api_key = self._secrets.get_secret(self._auth_ref)
        encoded = b64encode(f"{api_key}:".encode()).decode("ascii")
        request.headers["Authorization"] = f"Basic {encoded}"
        return request
