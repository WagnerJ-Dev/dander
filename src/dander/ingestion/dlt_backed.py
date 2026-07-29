"""dlt-backed extraction for declarative REST connectors.

dlt owns request execution, pagination, retry behavior, and response normalization. This adapter
translates Dander's validated `SourceConfig` into dlt's REST configuration while keeping secrets
behind the shared authentication strategy.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Annotated, Any

import httpx
from dlt.common.configuration.specs.base_configuration import NotResolved, configspec
from dlt.sources.helpers.rest_client.auth import AuthConfigBase
from dlt.sources.helpers.rest_client.paginators import (
    BasePaginator,
    HeaderLinkPaginator,
    JSONResponseCursorPaginator,
    OffsetPaginator,
    PageNumberPaginator,
    SinglePagePaginator,
)
from dlt.sources.rest_api import rest_api_source

from dander.ingestion.pagination import (
    CursorPagination,
    LinkHeaderPagination,
    NoPagination,
    OffsetPagination,
    PageNumberPagination,
)
from dander.ingestion.source import Endpoint, Source, SourceConfig
from dander.security.base import AuthStrategy  # noqa: TC001  # configspec resolves at runtime

if TYPE_CHECKING:
    from dlt.sources.rest_api.typing import Endpoint as DltEndpoint
    from dlt.sources.rest_api.typing import EndpointResource, RESTAPIConfig
    from requests import PreparedRequest


class EndpointNotFoundError(ValueError):
    """Raised when a connector does not declare a requested endpoint."""


class UnsupportedPaginationError(ValueError):
    """Raised when dlt cannot represent a declared pagination variation."""


@configspec
class DltAuthAdapter(AuthConfigBase):
    """Apply Dander's provider-neutral authentication strategy to every dlt request."""

    strategy: Annotated[AuthStrategy, NotResolved()] = None  # type: ignore[assignment]

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Copy authentication headers from an equivalent httpx request."""
        if request.url is None:
            raise ValueError("Cannot authenticate a request without a URL")
        candidate = httpx.Request(
            request.method or "GET",
            request.url,
            headers={str(key): str(value) for key, value in request.headers.items()},
        )
        authenticated = self.strategy.apply(candidate)
        request.headers.update(dict(authenticated.headers))
        return request


class DltRestSource(Source):
    """Adapt a standard REST connector to Dander's `Source` contract using dlt."""

    def __init__(self, config: SourceConfig, auth: AuthStrategy) -> None:
        super().__init__(config)
        self._auth = auth

    def discover(self) -> Mapping[str, Any]:
        """Return validated endpoint metadata without fetching source row values.

        Runtime schema inference remains dlt's responsibility during extraction. Returning only
        declarations here avoids persisting or logging sampled sensitive values.
        """
        return {
            endpoint.name: {
                "path": endpoint.path,
                "primary_key": list(endpoint.primary_key),
                "incremental_cursor": endpoint.incremental_cursor,
            }
            for endpoint in self.config.endpoints
        }

    def extract(self, endpoint: str, *, since: str | None = None) -> Iterator[Mapping[str, Any]]:
        """Yield normalized records for one configured endpoint."""
        rest_config = self.build_rest_config(endpoint, since=since)
        source = rest_api_source(rest_config, name=self.config.name).with_resources(endpoint)
        for item in source:
            if isinstance(item, Mapping):
                yield item
            else:
                raise TypeError(
                    f"Endpoint {endpoint!r} produced a non-mapping item of type "
                    f"{type(item).__name__}"
                )

    def build_rest_config(self, endpoint_name: str, *, since: str | None = None) -> RESTAPIConfig:
        """Translate one Dander endpoint into a dlt REST API configuration.

        This pure configuration boundary is public so callers can inspect a credential-free plan
        before execution. The returned object contains an authentication adapter for private
        sources and must never be logged.
        """
        endpoint = self._get_endpoint(endpoint_name)
        params: dict[str, Any] = {}
        paginator = self._build_paginator(endpoint, params)
        cursor_param = endpoint.cursor_param or endpoint.incremental_cursor
        if since is not None and cursor_param is not None:
            params[cursor_param] = since

        dlt_endpoint: DltEndpoint = {
            "path": endpoint.path.lstrip("/"),
            "paginator": paginator,
        }
        if endpoint.data_selector is not None:
            dlt_endpoint["data_selector"] = endpoint.data_selector
        if params:
            dlt_endpoint["params"] = params

        resource: EndpointResource = {
            "name": endpoint.name,
            "endpoint": dlt_endpoint,
        }
        if endpoint.primary_key:
            resource["primary_key"] = endpoint.primary_key

        return {
            "client": {
                "base_url": f"{self.config.base_url.rstrip('/')}/",
                "auth": DltAuthAdapter(self._auth),
            },
            "resources": [resource],
        }

    def _get_endpoint(self, endpoint_name: str) -> Endpoint:
        for endpoint in self.config.endpoints:
            if endpoint.name == endpoint_name:
                return endpoint
        raise EndpointNotFoundError(
            f"Connector {self.config.name!r} has no endpoint {endpoint_name!r}"
        )

    @staticmethod
    def _build_paginator(endpoint: Endpoint, params: dict[str, Any]) -> BasePaginator:
        pagination = endpoint.pagination
        if isinstance(pagination, NoPagination):
            return SinglePagePaginator()
        if isinstance(pagination, LinkHeaderPagination):
            if pagination.header_name.lower() != "link":
                raise UnsupportedPaginationError(
                    "dlt link-header pagination requires the standard Link header"
                )
            return HeaderLinkPaginator(links_next_key=pagination.rel)
        if isinstance(pagination, OffsetPagination):
            return OffsetPaginator(
                limit=pagination.page_size,
                offset_param=pagination.offset_param,
                limit_param=pagination.limit_param,
                total_path=None,
            )
        if isinstance(pagination, PageNumberPagination):
            params[pagination.size_param] = pagination.page_size
            return PageNumberPaginator(
                base_page=pagination.start_page,
                page_param=pagination.page_param,
                total_path=None,
            )
        if isinstance(pagination, CursorPagination):
            if pagination.size_param and pagination.page_size is not None:
                params[pagination.size_param] = pagination.page_size
            return JSONResponseCursorPaginator(
                cursor_path=pagination.next_cursor_path,
                cursor_param=pagination.cursor_param,
                stop_after_empty_page=True,
            )
        raise AssertionError(f"Unhandled pagination strategy: {type(pagination).__name__}")
