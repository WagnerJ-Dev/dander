"""Bearer-token authentication tests."""

from __future__ import annotations

import httpx

from dander.security import ApiKeyBearer


class SecretStore:
    def get_secret(self, reference: str) -> str:
        assert reference == "HUBSPOT_PRIVATE_APP_TOKEN"
        return "unit-secret"


def test_api_key_bearer_attaches_token_without_changing_other_headers() -> None:
    request = httpx.Request("GET", "https://api.hubapi.com", headers={"X-Test": "ok"})

    result = ApiKeyBearer(SecretStore(), "HUBSPOT_PRIVATE_APP_TOKEN").apply(request)

    assert result.headers["Authorization"] == "Bearer unit-secret"
    assert result.headers["X-Test"] == "ok"
