"""Bearer-token authentication for private-app and API-token providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dander.security.base import AuthStrategy

if TYPE_CHECKING:
    import httpx


class ApiKeyBearer(AuthStrategy):
    """Resolve one secret per request and attach it as a bearer token."""

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Attach the resolved token without retaining or logging its value."""
        token = self._secrets.get_secret(self._auth_ref)
        request.headers["Authorization"] = f"Bearer {token}"
        return request
