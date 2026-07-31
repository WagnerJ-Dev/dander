"""Authentication strategy for intentionally public endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dander.security.base import AuthStrategy

if TYPE_CHECKING:
    import httpx


class NoAuth(AuthStrategy):
    """Leave requests unchanged without resolving credentials."""

    def __init__(self) -> None:
        """Create a credential-free strategy."""

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Return the public request unchanged."""
        return request
