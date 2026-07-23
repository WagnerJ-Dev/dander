"""Unit tests for ``JoinType``/``JoinKeyPair``/``JoinSpec`` and `Edge.join` (DANDER-7).

Covers a connection's optional declarative join specification: intra-model boundary constraints
(closed join-type set, at least one key pair), left(`from`)/right(`to`) key-pair orientation and
order preservation, stable round-trip through both YAML and JSON, and backward compatibility of a
join-less edge (unchanged dump, no `join` key emitted). No SQL generation or execution, and no
cross-node field-existence validation, is in scope here (see DANDER-8) — model + serialization
only, matching the rest of `dander.pipeline.graph`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dander.pipeline.graph import (
    Edge,
    JoinKeyPair,
    JoinSpec,
    JoinType,
    Node,
    PipelineGraph,
    dump_graph_to_json,
    dump_graph_to_yaml,
    load_graph_from_json,
    load_graph_from_yaml,
)

if TYPE_CHECKING:
    from pathlib import Path

_YAML_DOC = """
name: candidate_ingest
nodes:
  - id: n1
    type: source
    name: extract_candidates
  - id: n2
    type: source
    name: extract_applications
edges:
  - from: n1
    to: n2
    join:
      type: left
      keys:
        - left: candidate_id
          right: candidate_id
      metadata:
        note: single-key
"""

_JSON_DOC = """
{
  "name": "candidate_ingest",
  "nodes": [
    {"id": "n1", "type": "source", "name": "extract_candidates"},
    {"id": "n2", "type": "source", "name": "extract_applications"}
  ],
  "edges": [
    {
      "from": "n1",
      "to": "n2",
      "join": {
        "type": "left",
        "keys": [{"left": "candidate_id", "right": "candidate_id"}],
        "metadata": {"note": "single-key"}
      }
    }
  ]
}
"""

_MULTI_KEY_YAML_DOC = """
name: candidate_ingest
nodes:
  - id: n1
    type: source
    name: extract_candidates
  - id: n2
    type: source
    name: extract_applications
edges:
  - from: n1
    to: n2
    join:
      type: inner
      keys:
        - left: candidate_id
          right: candidate_id
        - left: req_id
          right: requisition_id
        - left: region
          right: region_code
"""

_MULTI_KEY_JSON_DOC = """
{
  "name": "candidate_ingest",
  "nodes": [
    {"id": "n1", "type": "source", "name": "extract_candidates"},
    {"id": "n2", "type": "source", "name": "extract_applications"}
  ],
  "edges": [
    {
      "from": "n1",
      "to": "n2",
      "join": {
        "type": "inner",
        "keys": [
          {"left": "candidate_id", "right": "candidate_id"},
          {"left": "req_id", "right": "requisition_id"},
          {"left": "region", "right": "region_code"}
        ]
      }
    }
  ]
}
"""


def _assert_single_key_join(graph: PipelineGraph) -> None:
    edge = graph.edges[0]
    assert edge.join is not None
    assert edge.join.type is JoinType.LEFT
    assert len(edge.join.keys) == 1
    assert edge.join.keys[0].left == "candidate_id"
    assert edge.join.keys[0].right == "candidate_id"
    assert edge.join.metadata == {"note": "single-key"}


def test_edge_loads_single_key_join_from_yaml(tmp_path: Path) -> None:
    """An edge loads a single-key join (type + one key pair + metadata) from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_single_key_join(graph)


def test_edge_loads_single_key_join_from_json(tmp_path: Path) -> None:
    """An edge loads a single-key join (type + one key pair + metadata) from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_single_key_join(graph)


def _assert_multi_key_join_order(graph: PipelineGraph) -> None:
    edge = graph.edges[0]
    assert edge.join is not None
    assert edge.join.type is JoinType.INNER
    assert [kp.left for kp in edge.join.keys] == ["candidate_id", "req_id", "region"]
    assert [kp.right for kp in edge.join.keys] == [
        "candidate_id",
        "requisition_id",
        "region_code",
    ]


def test_edge_loads_multi_key_join_from_yaml_preserving_order(tmp_path: Path) -> None:
    """An edge loads a multi-key join from YAML with key-pair declaration order preserved."""
    path = tmp_path / "graph.yaml"
    path.write_text(_MULTI_KEY_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_multi_key_join_order(graph)


def test_edge_loads_multi_key_join_from_json_preserving_order(tmp_path: Path) -> None:
    """An edge loads a multi-key join from JSON with key-pair declaration order preserved."""
    path = tmp_path / "graph.json"
    path.write_text(_MULTI_KEY_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_multi_key_join_order(graph)


@pytest.mark.parametrize("value", ["inner", "left", "right", "full"])
def test_join_type_accepts_each_valid_value(value: str) -> None:
    """`JoinType` accepts each of the four documented values."""
    spec = JoinSpec.model_validate({"type": value, "keys": [{"left": "a", "right": "b"}]})
    assert spec.type is JoinType(value)


def test_join_type_rejects_invalid_value() -> None:
    """An unrecognized join type raises a `ValidationError` at the Pydantic boundary."""
    with pytest.raises(ValidationError):
        JoinSpec.model_validate({"type": "outer", "keys": [{"left": "a", "right": "b"}]})


def test_join_spec_rejects_empty_keys() -> None:
    """A `JoinSpec` with an empty `keys` list raises `ValidationError` (min_length=1)."""
    with pytest.raises(ValidationError):
        JoinSpec(type=JoinType.INNER, keys=[])


def test_join_spec_constructs_directly() -> None:
    """`JoinSpec`/`JoinKeyPair` construct directly with attribute names, not just on-disk keys."""
    spec = JoinSpec(
        type=JoinType.FULL,
        keys=[JoinKeyPair(left="a", right="b"), JoinKeyPair(left="c", right="d")],
    )
    assert spec.type is JoinType.FULL
    assert [(kp.left, kp.right) for kp in spec.keys] == [("a", "b"), ("c", "d")]
    assert spec.metadata == {}


def test_yaml_round_trip_is_stable_with_join(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for YAML, including join metadata."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    loaded = load_graph_from_yaml(path)

    dump_path = tmp_path / "dumped.yaml"
    dump_graph_to_yaml(loaded, dump_path)
    reloaded = load_graph_from_yaml(dump_path)
    assert loaded == reloaded

    dump_path_2 = tmp_path / "dumped2.yaml"
    dump_graph_to_yaml(reloaded, dump_path_2)
    reloaded_again = load_graph_from_yaml(dump_path_2)
    assert reloaded == reloaded_again


def test_json_round_trip_is_stable_with_join(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for JSON, including join metadata."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    loaded = load_graph_from_json(path)

    dump_path = tmp_path / "dumped.json"
    dump_graph_to_json(loaded, dump_path)
    reloaded = load_graph_from_json(dump_path)
    assert loaded == reloaded

    dump_path_2 = tmp_path / "dumped2.json"
    dump_graph_to_json(reloaded, dump_path_2)
    reloaded_again = load_graph_from_json(dump_path_2)
    assert reloaded == reloaded_again


def test_multi_key_join_round_trips_stably_both_formats(tmp_path: Path) -> None:
    """A multi-key join round-trips stably through both YAML and JSON."""
    yaml_path = tmp_path / "graph.yaml"
    yaml_path.write_text(_MULTI_KEY_YAML_DOC)
    yaml_loaded = load_graph_from_yaml(yaml_path)
    yaml_dump_path = tmp_path / "dumped.yaml"
    dump_graph_to_yaml(yaml_loaded, yaml_dump_path)
    assert load_graph_from_yaml(yaml_dump_path) == yaml_loaded

    json_path = tmp_path / "graph.json"
    json_path.write_text(_MULTI_KEY_JSON_DOC)
    json_loaded = load_graph_from_json(json_path)
    json_dump_path = tmp_path / "dumped.json"
    dump_graph_to_json(json_loaded, json_dump_path)
    assert load_graph_from_json(json_dump_path) == json_loaded


def test_join_less_edge_round_trips_unchanged_and_omits_join_key(tmp_path: Path) -> None:
    """A join-less edge round-trips equal and its dumped text carries no `join` key."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="task", name="a"), Node(id="n2", type="task", name="b")],
        edges=[Edge(source="n1", target="n2")],
    )
    assert graph.edges[0].join is None

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_text = yaml_path.read_text()
    assert "join" not in yaml_text
    reloaded_yaml = load_graph_from_yaml(yaml_path)
    assert reloaded_yaml == graph
    assert reloaded_yaml.edges[0].join is None

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_text = json_path.read_text()
    assert "join" not in json_text
    reloaded_json = load_graph_from_json(json_path)
    assert reloaded_json == graph
    assert reloaded_json.edges[0].join is None


def test_edge_with_join_dumps_nested_join_block(tmp_path: Path) -> None:
    """An edge with a join dumps a nested `join` block with `type`/`keys`, both formats."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="task", name="a"), Node(id="n2", type="task", name="b")],
        edges=[
            Edge(
                source="n1",
                target="n2",
                join=JoinSpec(type=JoinType.INNER, keys=[JoinKeyPair(left="x", right="y")]),
            )
        ],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_text = yaml_path.read_text()
    assert "join:" in yaml_text
    assert "type: inner" in yaml_text
    assert "left: x" in yaml_text
    assert "right: y" in yaml_text

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_text = json_path.read_text()
    assert '"join"' in json_text
    assert '"type": "inner"' in json_text
    assert '"left": "x"' in json_text
    assert '"right": "y"' in json_text
