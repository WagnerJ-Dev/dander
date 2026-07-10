"""GCP Secret Manager implementation of ``SecretStoreProvider``.

Structurally satisfies the Protocol in ``core.interfaces``. Every access is audited
(who/what/when/which-secret — never the value) per ``steering/01-security.md``.
"""

from __future__ import annotations


class GcpSecretStore:
    """Resolve secrets from GCP Secret Manager by resource name."""

    def get_secret(self, reference: str) -> str:
        """Return the secret value for a resource name like ``projects/…/secrets/NAME/versions/latest``."""
        raise NotImplementedError(
            "DANDER: fetch from Secret Manager and emit a credential-access audit log entry"
        )
