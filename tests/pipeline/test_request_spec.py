"""Unit tests for the source request/payload spec (DANDER-11).

Covers the pure reference/credential-shape helpers, `RequestSpec`'s reference-only validation
(Rule A for sensitive positions, Rule B credential-shape tripwire elsewhere), a `source` node
loading a full request spec from both YAML and JSON, round-trip stability in both formats, and
backward compatibility for a spec-less source node. All tokens below are synthetic
(`secret:demo_key`, `field:candidate_id`, a fake `Bearer` value, etc.) — no real/sensitive values.
No network; only `tmp_path` I/O, matching `test_node_config.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dander.pipeline.graph import (
    dump_graph_to_json,
    dump_graph_to_yaml,
    load_graph_from_json,
    load_graph_from_yaml,
)
from dander.pipeline.node_config import SourceNodeConfig
from dander.pipeline.request_spec import (
    HttpMethod,
    RequestSpec,
    is_field_reference,
    is_reference,
    is_secret_reference,
    looks_like_raw_credential,
)

if TYPE_CHECKING:
    from pathlib import Path

_YAML_DOC = """
name: source_request_example
nodes:
  - id: n1
    type: source
    name: extract_candidates
    config:
      endpoint: /candidates
      request:
        method: POST
        headers:
          Authorization: "secret:demo_key"
          Content-Type: "application/json"
        query_params:
          since: "field:updated_since"
        body:
          query: "field:graphql_query"
          variables:
            candidate_id: "field:candidate_id"
  - id: n2
    type: target
    name: load_candidates
    config:
      table: candidates
edges:
  - from: n1
    to: n2
"""

_JSON_DOC = """
{
  "name": "source_request_example",
  "nodes": [
    {
      "id": "n1",
      "type": "source",
      "name": "extract_candidates",
      "config": {
        "endpoint": "/candidates",
        "request": {
          "method": "POST",
          "headers": {
            "Authorization": "secret:demo_key",
            "Content-Type": "application/json"
          },
          "query_params": {"since": "field:updated_since"},
          "body": {
            "query": "field:graphql_query",
            "variables": {"candidate_id": "field:candidate_id"}
          }
        }
      }
    },
    {
      "id": "n2",
      "type": "target",
      "name": "load_candidates",
      "config": {"table": "candidates"}
    }
  ],
  "edges": [{"from": "n1", "to": "n2"}]
}
"""

_SPEC_LESS_YAML_DOC = """
name: spec_less_source
nodes:
  - id: n1
    type: source
    name: extract_candidates
    config:
      endpoint: /candidates
  - id: n2
    type: target
    name: load_candidates
edges:
  - from: n1
    to: n2
"""


def _assert_full_request_spec(source_config: SourceNodeConfig) -> None:
    assert source_config.request is not None
    request = source_config.request
    assert request.method == HttpMethod.POST
    assert request.headers == {
        "Authorization": "secret:demo_key",
        "Content-Type": "application/json",
    }
    assert request.query_params == {"since": "field:updated_since"}
    assert request.body == {
        "query": "field:graphql_query",
        "variables": {"candidate_id": "field:candidate_id"},
    }


# -- Method + serialization: YAML/JSON load, round-trip -----------------------------------------


def test_source_node_loads_full_request_spec_from_yaml(tmp_path: Path) -> None:
    """A `source` node loads method + headers + params + body from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)

    source_config = graph.nodes[0].config
    assert isinstance(source_config, SourceNodeConfig)
    _assert_full_request_spec(source_config)


def test_source_node_loads_full_request_spec_from_json(tmp_path: Path) -> None:
    """A `source` node loads method + headers + params + body from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)

    source_config = graph.nodes[0].config
    assert isinstance(source_config, SourceNodeConfig)
    _assert_full_request_spec(source_config)


def test_yaml_round_trip_is_stable_for_a_full_request_spec(tmp_path: Path) -> None:
    """Load -> dump -> load is stable for a source node with a full request spec (YAML)."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    loaded = load_graph_from_yaml(path)

    dump_path = tmp_path / "dumped.yaml"
    dump_graph_to_yaml(loaded, dump_path)
    reloaded = load_graph_from_yaml(dump_path)

    assert loaded == reloaded
    source_config = reloaded.nodes[0].config
    assert isinstance(source_config, SourceNodeConfig)
    _assert_full_request_spec(source_config)


def test_json_round_trip_is_stable_for_a_full_request_spec(tmp_path: Path) -> None:
    """Load -> dump -> load is stable for a source node with a full request spec (JSON)."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    loaded = load_graph_from_json(path)

    dump_path = tmp_path / "dumped.json"
    dump_graph_to_json(loaded, dump_path)
    reloaded = load_graph_from_json(dump_path)

    assert loaded == reloaded
    source_config = reloaded.nodes[0].config
    assert isinstance(source_config, SourceNodeConfig)
    _assert_full_request_spec(source_config)


# -- Backward compatibility: spec-less source node -----------------------------------------------


def test_spec_less_source_node_loads_and_round_trips_yaml(tmp_path: Path) -> None:
    """A source node with no `request` key loads with `request=None` and round-trips (YAML)."""
    path = tmp_path / "graph.yaml"
    path.write_text(_SPEC_LESS_YAML_DOC)
    loaded = load_graph_from_yaml(path)

    source_config = loaded.nodes[0].config
    assert isinstance(source_config, SourceNodeConfig)
    assert source_config.request is None

    dump_path = tmp_path / "dumped.yaml"
    dump_graph_to_yaml(loaded, dump_path)
    reloaded = load_graph_from_yaml(dump_path)
    assert reloaded == loaded
    assert reloaded.nodes[0].config.request is None  # type: ignore[union-attr]

    # On-disk cleanliness: no spurious `request: null` key for a spec-less source node.
    assert "request" not in dump_path.read_text()


def test_spec_less_source_node_loads_and_round_trips_json(tmp_path: Path) -> None:
    """A source node with no `request` key loads with `request=None` and round-trips (JSON)."""
    json_doc = """
    {
      "name": "spec_less_source",
      "nodes": [
        {"id": "n1", "type": "source", "name": "extract_candidates",
         "config": {"endpoint": "/candidates"}},
        {"id": "n2", "type": "target", "name": "load_candidates"}
      ],
      "edges": [{"from": "n1", "to": "n2"}]
    }
    """
    path = tmp_path / "graph.json"
    path.write_text(json_doc)
    loaded = load_graph_from_json(path)

    source_config = loaded.nodes[0].config
    assert isinstance(source_config, SourceNodeConfig)
    assert source_config.request is None

    dump_path = tmp_path / "dumped.json"
    dump_graph_to_json(loaded, dump_path)
    reloaded = load_graph_from_json(dump_path)
    assert reloaded == loaded
    assert reloaded.nodes[0].config.request is None  # type: ignore[union-attr]
    assert '"request"' not in dump_path.read_text()


def test_request_spec_defaults_to_get_when_not_specified() -> None:
    """A `RequestSpec` constructed with no `method` defaults to `GET` (AC #3 sensible default)."""
    assert RequestSpec().method == HttpMethod.GET


# -- RequestSpec validation: reference contract -------------------------------------------------


def test_request_spec_accepts_references_in_headers_params_and_body() -> None:
    """References in headers/params/body (incl. nested body leaves) are all accepted."""
    spec = RequestSpec(
        method=HttpMethod.POST,
        headers={"Authorization": "secret:demo_key", "Content-Type": "application/json"},
        query_params={"since": "field:updated_since"},
        body={"query": "field:graphql_query", "variables": {"candidate_id": "field:candidate_id"}},
    )
    assert spec.headers["Authorization"] == "secret:demo_key"


def test_request_spec_accepts_benign_static_header() -> None:
    """A benign static, non-sensitive, non-credential-shaped header value is accepted."""
    spec = RequestSpec(headers={"Content-Type": "application/json"})
    assert spec.headers["Content-Type"] == "application/json"


def test_request_spec_accepts_plain_string_body() -> None:
    """A benign raw string body template is accepted."""
    spec = RequestSpec(body="query { candidate(id: field:candidate_id) }")
    assert spec.body is not None


def test_request_spec_rejects_inline_literal_in_sensitive_header_rule_a() -> None:
    """An inline literal (not a reference) in a sensitive header position is rejected (Rule A)."""
    with pytest.raises(ValidationError) as exc_info:
        RequestSpec(headers={"Authorization": "Bearer not-a-real-token-1234567890"})

    message = str(exc_info.value)
    assert "Authorization" in message
    assert "not-a-real-token-1234567890" not in message


def test_request_spec_rejects_inline_literal_in_sensitive_param_rule_a() -> None:
    """An inline literal (not a reference) in a sensitive query-param position is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        RequestSpec(query_params={"token": "not-a-reference-value"})

    message = str(exc_info.value)
    assert "token" in message
    assert "not-a-reference-value" not in message


def test_request_spec_rejects_credential_shaped_literal_in_plain_position_rule_b() -> None:
    """A credential-shaped literal in a non-sensitive position is rejected (Rule B)."""
    with pytest.raises(ValidationError) as exc_info:
        RequestSpec(headers={"X-Debug-Token": "sk_fake-not-a-real-key-000000"})

    message = str(exc_info.value)
    assert "X-Debug-Token" in message
    assert "sk_fake-not-a-real-key-000000" not in message


def test_request_spec_rejects_credential_shaped_literal_in_body_leaf_rule_b() -> None:
    """A credential-shaped literal nested in the body template is rejected (Rule B)."""
    with pytest.raises(ValidationError) as exc_info:
        RequestSpec(body={"variables": {"token": "AKIAfake-not-a-real-access-key"}})

    message = str(exc_info.value)
    assert "body" in message
    assert "AKIAfake-not-a-real-access-key" not in message


# -- Pure helper unit tests ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("secret:demo_key", True),
        ("env:API_KEY", True),
        ("projects/my-proj/secrets/my-secret/versions/latest", True),
        ("field:candidate_id", False),
        ("just-a-plain-string", False),
        ("", False),
    ],
)
def test_is_secret_reference(value: str, expected: bool) -> None:
    assert is_secret_reference(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("field:candidate_id", True),
        ("{{ candidate_id }}", True),
        ("{{candidate_id}}", True),
        ("secret:demo_key", False),
        ("not-a-field-ref", False),
    ],
)
def test_is_field_reference(value: str, expected: bool) -> None:
    assert is_field_reference(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("secret:demo_key", True),
        ("field:candidate_id", True),
        ("application/json", False),
        ("", False),
    ],
)
def test_is_reference(value: str, expected: bool) -> None:
    assert is_reference(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Bearer not-a-real-token-1234567890", True),
        ("Basic dXNlcjpwYXNz1234", True),
        ("-----BEGIN PRIVATE KEY-----", True),
        ("sk_fake-not-a-real-key-000000", True),
        ("AKIAfake-not-a-real-access-key", True),
        ("ghp_fake-not-a-real-token-000", True),
        ("xoxb-fake-not-a-real-slack-token", True),
        ("a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5", True),
        ("application/json", False),
        ("GET", False),
        ("this is a normal sentence with spaces", False),
        ("reallylongwordwithonlylettersandnodigitsatall", False),
        ("secret:demo_key", False),
        ("field:candidate_id", False),
        ("", False),
    ],
)
def test_looks_like_raw_credential(value: str, expected: bool) -> None:
    assert looks_like_raw_credential(value) is expected
