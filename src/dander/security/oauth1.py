"""RFC 5849 OAuth 1.0a token-based authentication for NetSuite-style APIs."""

from __future__ import annotations

from base64 import b64encode
from hashlib import sha256
from hmac import new as new_hmac
from time import time
from typing import TYPE_CHECKING
from urllib.parse import quote

from dander.security.base import AuthStrategy

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx

    from dander.core.interfaces import SecretStoreProvider


class OAuth1TBA(AuthStrategy):
    """Sign each request with HMAC-SHA256 OAuth 1.0a token credentials."""

    def __init__(
        self,
        secrets: SecretStoreProvider,
        *,
        account_id: str,
        consumer_key_ref: str,
        consumer_secret_ref: str,
        token_id_ref: str,
        token_secret_ref: str,
        nonce: Callable[[], str] | None = None,
        clock: Callable[[], float] = time,
    ) -> None:
        super().__init__(secrets, token_secret_ref)
        if not account_id.strip():
            raise ValueError("OAuth1 TBA account_id must be non-empty")
        self._account_id = account_id
        self._consumer_key_ref = consumer_key_ref
        self._consumer_secret_ref = consumer_secret_ref
        self._token_id_ref = token_id_ref
        self._token_secret_ref = token_secret_ref
        self._nonce = nonce or _random_nonce
        self._clock = clock

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Attach an RFC 5849 Authorization header without retaining credentials."""
        consumer_key = self._secrets.get_secret(self._consumer_key_ref)
        consumer_secret = self._secrets.get_secret(self._consumer_secret_ref)
        token_id = self._secrets.get_secret(self._token_id_ref)
        token_secret = self._secrets.get_secret(self._token_secret_ref)
        oauth = {
            "oauth_consumer_key": consumer_key,
            "oauth_nonce": self._nonce(),
            "oauth_signature_method": "HMAC-SHA256",
            "oauth_timestamp": str(int(self._clock())),
            "oauth_token": token_id,
            "oauth_version": "1.0",
        }
        parameters = [*request.url.params.multi_items(), *oauth.items()]
        normalized = "&".join(
            f"{key}={value}"
            for key, value in sorted((_encode(key), _encode(value)) for key, value in parameters)
        )
        base_string = "&".join(
            (
                _encode(request.method.upper()),
                _encode(_base_uri(request.url)),
                _encode(normalized),
            )
        )
        signing_key = f"{_encode(consumer_secret)}&{_encode(token_secret)}"
        signature = b64encode(
            new_hmac(signing_key.encode(), base_string.encode(), sha256).digest()
        ).decode("ascii")
        header_values = {"realm": self._account_id, **oauth, "oauth_signature": signature}
        request.headers["Authorization"] = "OAuth " + ", ".join(
            f'{key}="{_encode(value)}"' for key, value in header_values.items()
        )
        return request


def _base_uri(url: httpx.URL) -> str:
    scheme = url.scheme.lower()
    host = url.host.lower()
    port = url.port
    authority = host
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        authority = f"{host}:{port}"
    return f"{scheme}://{authority}{url.path or '/'}"


def _encode(value: str) -> str:
    return quote(value, safe="~-._")


def _random_nonce() -> str:
    from secrets import token_hex

    return token_hex(16)
