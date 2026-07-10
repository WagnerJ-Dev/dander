"""Core provider interfaces — the abstraction spine.

Application code depends on these Protocols, never on a concrete cloud. GCP implementations live
now; AWS/Azure implementations can be added later without touching callers. See
``steering/02-engineering.md`` (interfaces first) and ``steering/01-security.md``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretStoreProvider(Protocol):
    """Resolves a secret *value* from a backing store given its reference.

    Implementations never accept a literal secret and never log the value. The reference is an
    indirection (e.g. a Secret Manager resource name or an env var name), never the secret itself.
    """

    def get_secret(self, reference: str) -> str:
        """Return the secret value identified by ``reference``."""
        ...


@runtime_checkable
class ComputeProvider(Protocol):
    """Targets a compute environment for running connectors (e.g. Cloud Run jobs)."""

    def submit(self, job_name: str, args: list[str]) -> str:
        """Submit a job and return an identifier for tracking its execution."""
        ...
