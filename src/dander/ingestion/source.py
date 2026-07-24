"""The ``Source`` abstraction — the common contract for BOTH ingestion paths.

Per the hybrid decision (see the Decision Log in ``steering/00-project-overview.md``): standard
REST sources are implemented on dlt; gnarly enterprise sources (Workday, NetSuite, Xactly) are
hand-rolled. Both implement ``Source``, so the writer, state, and orchestration layers never care
which path produced the records.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from dander.ingestion.pagination import NoPagination, PaginationStrategy

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class Endpoint(BaseModel):
    """One retrievable entity within a source (loaded from the connector YAML).

    Attributes:
        name: Endpoint identifier, unique within its `SourceConfig`.
        path: Path appended to `SourceConfig.base_url` to retrieve this endpoint.
        pagination: The pagination strategy for this endpoint (see
            `dander.ingestion.pagination.PaginationStrategy`), mirroring the strategy pattern
            already used for auth (`steering/01-security.md`). Defaults to `NoPagination` — a
            single request, no paging. A bare string (e.g. ``"link_header"``) is accepted as
            shorthand for ``{"kind": "link_header"}`` and coerced to the matching strategy; this
            keeps existing connector YAML (`connectors/greenhouse.yaml`) loading unchanged.
        incremental_cursor: Response field name used as the incremental watermark, or `None` for
            a full-refresh endpoint. **Legacy, narrow form (pre-DANDER-18):** just a field name,
            with no cursor *kind* (timestamp / sequence / opaque token) and disconnected from the
            pipeline graph model. Superseded by the node-level `dander.pipeline.graph.
            CursorStrategy` (attached via `Node.cursor`), which adds the kind plus boundary
            validation and is surfaced at the graph level per `steering/00-project-overview.md`'s
            control-table/idempotency design. Kept here unchanged so existing connector YAML
            (e.g. `connectors/greenhouse.yaml`) keeps loading; a caller that wants a
            `CursorStrategy` from a legacy endpoint should call
            `CursorStrategy.from_incremental_cursor(endpoint.incremental_cursor)` rather than
            reading this field directly for new code.
        primary_key: Field name(s) forming this endpoint's business key.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    path: str
    pagination: PaginationStrategy = Field(default_factory=NoPagination)
    incremental_cursor: str | None = None
    primary_key: list[str] = Field(default_factory=list)

    @field_validator("pagination", mode="before")
    @classmethod
    def _coerce_bare_pagination_kind(cls, value: object) -> object:
        """Coerce a bare pagination-kind string into its object shorthand.

        Lets existing connector YAML keep writing ``pagination: none`` / ``pagination:
        link_header`` rather than requiring the full ``{"kind": ...}`` object form for every
        endpoint. Dicts and already-typed strategy instances pass through untouched; the
        discriminated union in `dander.ingestion.pagination.PaginationStrategy` still rejects an
        out-of-set kind or a kind missing a required param (e.g. `cursor` without
        `next_cursor_path`, which has no safe universal default and so has no shorthand).

        Args:
            value: The raw `pagination` value being validated.

        Returns:
            `{"kind": value}` if `value` is a `str`; otherwise `value` unchanged.
        """
        if isinstance(value, str):
            return {"kind": value}
        return value


class BackoffKind(StrEnum):
    """The closed set of retry-backoff curves a `RateLimitConfig` may declare.

    A `StrEnum` (matching the `PaginationKind`/`TransformationKind`/`JoinType`/`WriteMode`
    convention elsewhere in the codebase — see `dander.ingestion.pagination.PaginationKind` and
    `dander.writer.base.WriteMode`) so the ingestion runtime gets a named, importable type to
    branch on, while the value still serializes to/from its plain string stably in YAML and JSON.
    An unknown value fails validation automatically rather than silently falling through.

    Attributes:
        FIXED: Constant delay between retries.
        EXPONENTIAL: Exponentially increasing delay between retries (the safer default against a
            throttling API).
    """

    FIXED = "fixed"
    EXPONENTIAL = "exponential"


class RateLimitConfig(BaseModel):
    """Declarative per-source rate-limit / backoff policy.

    Satisfies the per-source throttling requirement in `steering/02-engineering.md` ("Rate-limit/
    backoff per source (Marketo & Salesforce throttle). Retries are bounded and logged.") by
    giving that requirement a config home. This model is **declaration-only**: no throttling,
    sleeping, or retrying is performed here — that is the ingestion runtime's responsibility (a
    later ticket), which will read this policy off `SourceConfig.rate_limit`.

    Attributes:
        requests_per_second: Steady-state request rate allowed against the source. Must be
            strictly positive (`gt=0`) — a rate of `0` would mean the source can never be read,
            which is never the intent of declaring a policy. Conservative default of `1.0`.
        burst: Maximum number of requests permitted in a short burst above the steady rate.
            `ge=1` (a burst of `0` is nonsensical); default `1` means no burst allowance.
        backoff: Which retry-backoff curve to use when throttled. Defaults to
            `BackoffKind.EXPONENTIAL`, the safer choice against a throttling API.
        max_retries: Bounded retry count. `ge=0` (explicitly allows disabling retries) and
            `le=10` (a sane upper bound so a misconfigured source cannot retry unboundedly);
            default `5`.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    requests_per_second: float = Field(default=1.0, gt=0)
    burst: int = Field(default=1, ge=1)
    backoff: BackoffKind = BackoffKind.EXPONENTIAL
    max_retries: int = Field(default=5, ge=0, le=10)


class SourceConfig(BaseModel):
    """Declarative definition of a source system and its endpoints."""

    name: str
    base_url: str
    auth_strategy: str = Field(description="Registered AuthStrategy key, e.g. 'api_key_basic'")
    auth_ref: str = Field(
        description="Secret reference the AuthStrategy resolves (never the value)"
    )
    endpoints: list[Endpoint] = Field(default_factory=list)
    rate_limit: RateLimitConfig | None = Field(
        default=None,
        description="Optional per-source rate-limit/backoff policy; None means unconstrained.",
    )


class Source(ABC):
    """Extracts records from one source system, endpoint by endpoint."""

    def __init__(self, config: SourceConfig) -> None:
        self.config = config

    @abstractmethod
    def discover(self) -> Mapping[str, Any]:
        """Return an inferred schema per endpoint (feeds type casting + the catalog spine)."""

    @abstractmethod
    def extract(self, endpoint: str, *, since: str | None = None) -> Iterator[Mapping[str, Any]]:
        """Yield records for ``endpoint``, optionally bounded by incremental cursor ``since``."""
