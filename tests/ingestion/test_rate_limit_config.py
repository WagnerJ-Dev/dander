"""Unit tests for the per-source rate-limit/backoff config model (DANDER-13).

Covers: a source loading a full `rate_limit` block, boundary-constraint rejection of invalid
values (`requests_per_second`, `burst`, `max_retries`, and an unknown `backoff` kind), round-trip
stability through both JSON and YAML, and the config-less (backward-compatible) source path.
Pure model logic only — no network, no fixtures carrying secrets or sample data
(`steering/01-security.md`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from dander.ingestion.source import BackoffKind, RateLimitConfig, SourceConfig


def _sample_source_config(*, rate_limit: RateLimitConfig | None) -> SourceConfig:
    return SourceConfig(
        name="example",
        base_url="https://example.test/v1",
        auth_strategy="api_key_basic",
        auth_ref="env:EXAMPLE_API_KEY",
        rate_limit=rate_limit,
    )


def test_source_loads_its_rate_limit_config() -> None:
    cfg = SourceConfig.model_validate(
        {
            "name": "example",
            "base_url": "https://example.test/v1",
            "auth_strategy": "api_key_basic",
            "auth_ref": "env:EXAMPLE_API_KEY",
            "rate_limit": {
                "requests_per_second": 5.0,
                "burst": 10,
                "backoff": "fixed",
                "max_retries": 3,
            },
        }
    )

    assert cfg.rate_limit is not None
    assert cfg.rate_limit.requests_per_second == 5.0
    assert cfg.rate_limit.burst == 10
    assert cfg.rate_limit.backoff == BackoffKind.FIXED
    assert cfg.rate_limit.max_retries == 3


def test_rate_limit_config_has_conservative_defaults() -> None:
    rate_limit = RateLimitConfig()

    assert rate_limit.requests_per_second == 1.0
    assert rate_limit.burst == 1
    assert rate_limit.backoff == BackoffKind.EXPONENTIAL
    assert rate_limit.max_retries == 5


@pytest.mark.parametrize(
    "overrides",
    [
        {"requests_per_second": 0},
        {"requests_per_second": -1.0},
        {"burst": 0},
        {"burst": -1},
        {"max_retries": -1},
        {"max_retries": 11},
        {"backoff": "linear"},
    ],
)
def test_boundary_constraints_reject_invalid_values(overrides: dict[str, object]) -> None:
    payload = {
        "requests_per_second": 1.0,
        "burst": 1,
        "backoff": "fixed",
        "max_retries": 5,
        **overrides,
    }
    with pytest.raises(ValidationError):
        RateLimitConfig.model_validate(payload)


@pytest.mark.parametrize("serializer", ["json", "yaml"])
def test_round_trip_stability(serializer: str) -> None:
    cfg = _sample_source_config(
        rate_limit=RateLimitConfig(
            requests_per_second=2.5, burst=5, backoff=BackoffKind.FIXED, max_retries=2
        )
    )

    dumped = cfg.model_dump(mode="json")
    if serializer == "json":
        reloaded_payload = json.loads(json.dumps(dumped))
    else:
        reloaded_payload = yaml.safe_load(yaml.safe_dump(dumped))

    reloaded = SourceConfig.model_validate(reloaded_payload)
    assert reloaded == cfg
    assert reloaded.rate_limit == cfg.rate_limit


def test_config_less_source_is_unchanged_and_round_trips() -> None:
    cfg = _sample_source_config(rate_limit=None)
    assert cfg.rate_limit is None

    # Loads from a greenhouse-style dict with no `rate_limit` key at all.
    loaded = SourceConfig.model_validate(
        {
            "name": "example",
            "base_url": "https://example.test/v1",
            "auth_strategy": "api_key_basic",
            "auth_ref": "env:EXAMPLE_API_KEY",
        }
    )
    assert loaded.rate_limit is None
    assert loaded == cfg

    dumped = loaded.model_dump(mode="json")
    reloaded = SourceConfig.model_validate(json.loads(json.dumps(dumped)))
    assert reloaded == loaded
    assert reloaded.rate_limit is None


def test_greenhouse_connector_yaml_has_no_rate_limit_block() -> None:
    connector_path = Path(__file__).parents[2] / "connectors" / "greenhouse.yaml"
    cfg = SourceConfig.model_validate(yaml.safe_load(connector_path.read_text()))

    assert cfg.rate_limit is None
