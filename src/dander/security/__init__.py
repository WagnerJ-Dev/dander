"""Security module: secret resolution and pluggable authentication strategies."""

from dander.security.api_key import ApiKeyBasic
from dander.security.base import AuthStrategy
from dander.security.no_auth import NoAuth
from dander.security.oauth import OAuth2ClientCredentials, OAuthTokenError
from dander.security.secret_manager import (
    DefaultSecretStore,
    EnvironmentSecretStore,
    GcpSecretStore,
    SecretResolutionError,
)

__all__ = [
    "ApiKeyBasic",
    "AuthStrategy",
    "DefaultSecretStore",
    "EnvironmentSecretStore",
    "GcpSecretStore",
    "NoAuth",
    "OAuth2ClientCredentials",
    "OAuthTokenError",
    "SecretResolutionError",
]
