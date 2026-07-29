"""Fail-closed preparation for no-billing BigQuery Sandbox projects."""

from __future__ import annotations

import re
from typing import Protocol, cast

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import bigquery
from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError

_BILLING_SCOPE = "https://www.googleapis.com/auth/cloud-billing.readonly"
_PROJECT_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class SandboxSafetyError(RuntimeError):
    """Raised when Dander cannot prove a project is safe for strict sandbox mode."""


class _Response(Protocol):
    status_code: int

    def json(self) -> object:
        """Decode a JSON response."""


class _Session(Protocol):
    def get(self, url: str, *, timeout: float) -> _Response:
        """Issue an authenticated GET request."""


class _BillingVerifier(Protocol):
    def require_disabled(self, project: str) -> None:
        """Fail unless billing is explicitly disabled."""


class _BillingInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    billing_enabled: StrictBool


class GcpBillingVerifier:
    """Require the Cloud Billing API to explicitly report billing as disabled."""

    def __init__(self, session: _Session | None = None) -> None:
        if session is None:
            try:
                credentials, _ = google.auth.default(scopes=[_BILLING_SCOPE])
                session = cast(
                    "_Session",
                    AuthorizedSession(credentials),  # type: ignore[no-untyped-call]
                )
            except Exception as error:
                raise SandboxSafetyError(
                    "Application Default Credentials are required to verify billing"
                ) from error
        self._session = session

    def require_disabled(self, project: str) -> None:
        """Fail unless billing is explicitly disabled for ``project``."""
        if not _PROJECT_ID.fullmatch(project):
            raise SandboxSafetyError(f"Invalid GCP project id: {project!r}")
        try:
            response = self._session.get(
                f"https://cloudbilling.googleapis.com/v1/projects/{project}/billingInfo",
                timeout=15.0,
            )
        except Exception as error:
            raise SandboxSafetyError(
                "Could not reach Cloud Billing to verify that billing is disabled"
            ) from error
        if response.status_code != 200:
            raise SandboxSafetyError(
                "Could not verify that billing is disabled "
                f"(Cloud Billing API returned HTTP {response.status_code})"
            )
        try:
            payload = response.json()
            info = _BillingInfo.model_validate(
                {"billing_enabled": payload["billingEnabled"]} if isinstance(payload, dict) else {}
            )
        except (KeyError, TypeError, ValidationError, ValueError) as error:
            raise SandboxSafetyError(
                "Cloud Billing returned an invalid response; refusing sandbox execution"
            ) from error
        if info.billing_enabled:
            raise SandboxSafetyError(
                f"Billing is enabled for project {project!r}; refusing strict $0 sandbox execution"
            )


class SandboxDataset:
    """Create the raw dataset only after the no-billing safety check passes."""

    def __init__(
        self,
        *,
        verifier: _BillingVerifier | None = None,
        client: object | None = None,
    ) -> None:
        self._verifier = verifier or GcpBillingVerifier()
        self._client = cast("bigquery.Client | None", client)

    def prepare(self, project: str, dataset: str) -> None:
        """Verify billing is disabled, then create the dataset if absent."""
        self._verifier.require_disabled(project)
        if not re.fullmatch(r"^[A-Za-z_][A-Za-z0-9_]*$", dataset):
            raise SandboxSafetyError(f"Invalid BigQuery dataset id: {dataset!r}")
        resource = bigquery.Dataset(f"{project}.{dataset}")
        client = self._client or bigquery.Client(project=project)
        try:
            client.create_dataset(resource, exists_ok=True)
        except Exception as error:
            raise SandboxSafetyError(
                f"Could not create or access BigQuery dataset {project}.{dataset}"
            ) from error
