"""Authentication strategies — one interface, one strategy per auth model.

The named source systems do not share an auth model, so auth is pluggable (see the strategy table
in ``steering/01-security.md``). Strategies resolve credentials via a ``SecretStoreProvider`` and
never hold or log literal secrets.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

    from dander.core.interfaces import SecretStoreProvider


class AuthStrategy(ABC):
    """Applies authentication to outgoing requests for a single source system."""

    def __init__(self, secrets: SecretStoreProvider, auth_ref: str) -> None:
        self._secrets = secrets
        self._auth_ref = auth_ref

    @abstractmethod
    def apply(self, request: httpx.Request) -> httpx.Request:
        """Return ``request`` with authentication applied (headers, params, or signature)."""

    def refresh(self) -> None:
        """Refresh cached tokens if the strategy uses them. Default: no-op."""
        return None
