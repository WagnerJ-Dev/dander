"""Runtime configuration, loaded from the environment — never hard-coded.

This holds non-sensitive settings and secret *references* only; secret values are resolved at use
time via a ``SecretStoreProvider``. See ``steering/01-security.md``.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-derived settings (see ``.env.example`` for the keys)."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    bq_dataset_raw: str = "raw"
    bq_dataset_staging: str = "staging"
    bq_dataset_marts: str = "marts"
