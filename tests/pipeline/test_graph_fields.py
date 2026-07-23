"""Unit tests for the `NodeField` schema on `Node` (declaration + YAML/JSON round-trip).

Fixtures use synthetic type/label tokens only (e.g. `type: STRING`, `metadata: {sensitivity:
pii}`) -- never a real field value or sample datum, per `steering/01-security.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dander.pipeline.graph import (
    Node,
    NodeField,
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
    config:
      endpoint: /candidates
    fields:
      - name: candidate_id
        type: STRING
        nullable: false
        description: Unique candidate identifier.
        metadata:
          sensitivity: pii
      - name: applied_at
        type: TIMESTAMP
  - id: n2
    type: target
    name: load_candidates
edges:
  - from: n1
    to: n2
"""

_JSON_DOC = """
{
  "name": "candidate_ingest",
  "nodes": [
    {
      "id": "n1",
      "type": "source",
      "name": "extract_candidates",
      "config": {"endpoint": "/candidates"},
      "fields": [
        {
          "name": "candidate_id",
          "type": "STRING",
          "nullable": false,
          "description": "Unique candidate identifier.",
          "metadata": {"sensitivity": "pii"}
        },
        {"name": "applied_at", "type": "TIMESTAMP"}
      ]
    },
    {"id": "n2", "type": "target", "name": "load_candidates"}
  ],
  "edges": [
    {"from": "n1", "to": "n2"}
  ]
}
"""


def _assert_expected_fields(graph: PipelineGraph) -> None:
    fielded, fieldless = graph.nodes
    assert fielded.id == "n1"
    assert len(fielded.fields) == 2

    candidate_id = fielded.fields[0]
    assert candidate_id.name == "candidate_id"
    assert candidate_id.type == "STRING"
    assert candidate_id.nullable is False
    assert candidate_id.description == "Unique candidate identifier."
    assert candidate_id.metadata == {"sensitivity": "pii"}

    applied_at = fielded.fields[1]
    assert applied_at.name == "applied_at"
    assert applied_at.type == "TIMESTAMP"
    assert applied_at.nullable is True
    assert applied_at.description is None
    assert applied_at.metadata == {}

    assert fieldless.id == "n2"
    assert fieldless.fields == []


def test_node_loads_declared_fields_from_yaml(tmp_path: Path) -> None:
    """A node loads its declared `fields` (with `nullable`/`description`/`metadata`) from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_expected_fields(graph)


def test_node_loads_declared_fields_from_json(tmp_path: Path) -> None:
    """A node loads its declared `fields` (with `nullable`/`description`/`metadata`) from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_expected_fields(graph)


def test_yaml_round_trip_is_stable_with_fields(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for YAML, including field `metadata`."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    loaded = load_graph_from_yaml(path)

    dump_path = tmp_path / "dumped.yaml"
    dump_graph_to_yaml(loaded, dump_path)
    reloaded = load_graph_from_yaml(dump_path)

    assert loaded == reloaded
    assert reloaded.nodes[0].fields[0].metadata == {"sensitivity": "pii"}


def test_json_round_trip_is_stable_with_fields(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for JSON, including field `metadata`."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    loaded = load_graph_from_json(path)

    dump_path = tmp_path / "dumped.json"
    dump_graph_to_json(loaded, dump_path)
    reloaded = load_graph_from_json(dump_path)

    assert loaded == reloaded
    assert reloaded.nodes[0].fields[0].metadata == {"sensitivity": "pii"}


def test_fieldless_node_defaults_to_empty_fields() -> None:
    """A node with no declared fields still validates, with `fields` defaulting to `[]`."""
    node = Node(id="n1", type="task", name="a")
    assert node.fields == []


def test_fieldless_node_default_fields_are_independent_per_instance() -> None:
    """The `fields` default is a fresh list per instance (no shared mutable default)."""
    node_a = Node(id="n1", type="task", name="a")
    node_b = Node(id="n2", type="task", name="b")
    node_a.fields.append(NodeField(name="x", type="STRING"))
    assert node_b.fields == []


def test_graph_mixing_fielded_and_fieldless_nodes_round_trips(tmp_path: Path) -> None:
    """A graph mixing a fielded and a fieldless node round-trips with equality preserved."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            Node(
                id="n1",
                type="source",
                name="a",
                fields=[
                    NodeField(name="x", type="STRING", metadata={"sensitivity": "pii"}),
                ],
            ),
            Node(id="n2", type="target", name="b"),
        ],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    reloaded_yaml = load_graph_from_yaml(yaml_path)
    assert graph == reloaded_yaml

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    reloaded_json = load_graph_from_json(json_path)
    assert graph == reloaded_json
