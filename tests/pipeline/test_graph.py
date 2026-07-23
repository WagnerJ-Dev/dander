"""Unit tests for ``dander.pipeline.graph`` (Node/Edge/PipelineGraph + YAML/JSON round-trip)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dander.pipeline.graph import (
    Edge,
    FieldMapping,
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
    config:
      endpoint: /candidates
  - id: n2
    type: target
    name: load_candidates
edges:
  - from: n1
    to: n2
    metadata:
      note: full-refresh
    mappings:
      - source: candidate_id
        target: candidate_id
        metadata:
          note: primary-key
      - source: full_name
        target: name
"""

_JSON_DOC = """
{
  "name": "candidate_ingest",
  "nodes": [
    {
      "id": "n1",
      "type": "source",
      "name": "extract_candidates",
      "config": {"endpoint": "/candidates"}
    },
    {"id": "n2", "type": "target", "name": "load_candidates"}
  ],
  "edges": [
    {
      "from": "n1",
      "to": "n2",
      "metadata": {"note": "full-refresh"},
      "mappings": [
        {"source": "candidate_id", "target": "candidate_id", "metadata": {"note": "primary-key"}},
        {"source": "full_name", "target": "name"}
      ]
    }
  ]
}
"""


def _assert_expected_graph(graph: PipelineGraph) -> None:
    assert graph.name == "candidate_ingest"
    assert [n.id for n in graph.nodes] == ["n1", "n2"]
    assert graph.nodes[0].config == {"endpoint": "/candidates"}
    assert graph.nodes[1].config == {}
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.source == "n1"
    assert edge.target == "n2"
    assert edge.metadata == {"note": "full-refresh"}
    assert len(edge.mappings) == 2
    assert [m.source for m in edge.mappings] == ["candidate_id", "full_name"]
    assert [m.target for m in edge.mappings] == ["candidate_id", "name"]
    assert edge.mappings[0].metadata == {"note": "primary-key"}
    assert edge.mappings[1].metadata == {}


def test_load_multi_node_edge_graph_from_yaml(tmp_path: Path) -> None:
    """A valid multi-node/multi-edge graph loads correctly from a YAML file."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_expected_graph(graph)


def test_load_multi_node_edge_graph_from_json(tmp_path: Path) -> None:
    """A valid multi-node/multi-edge graph loads correctly from a JSON file."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_expected_graph(graph)


def test_edge_alias_populates_by_alias_and_by_attribute_name() -> None:
    """`Edge` accepts both the on-disk `from`/`to` keys and the Python attribute names."""
    by_alias = Edge.model_validate({"from": "a", "to": "b"})
    by_name = Edge(source="a", target="b")
    assert by_alias == by_name
    assert by_alias.source == "a"
    assert by_alias.target == "b"


def test_edge_dump_emits_reserved_keyword_keys_not_attribute_names() -> None:
    """Serializing an `Edge` emits `from`/`to`, never a literal `source`/`target` key."""
    edge = Edge(source="a", target="b")
    dumped = edge.model_dump(by_alias=True)
    assert dumped == {"from": "a", "to": "b", "metadata": {}, "mappings": [], "join": None}
    assert "source" not in dumped
    assert "target" not in dumped


def test_node_config_accepts_params_alias() -> None:
    """`Node` accepts the `params` key as an alias for the canonical `config` attribute."""
    node = Node.model_validate({"id": "n1", "type": "task", "name": "t", "params": {"a": 1}})
    assert node.config == {"a": 1}


def test_node_and_edge_defaults_are_independent_empty_containers() -> None:
    """Default `config`/`metadata` dicts are fresh per instance (no mutable default args)."""
    node_a = Node(id="n1", type="task", name="a")
    node_b = Node(id="n2", type="task", name="b")
    node_a.config["mutated"] = True
    assert node_b.config == {}

    edge_a = Edge(source="n1", target="n2")
    edge_b = Edge(source="n2", target="n1")
    edge_a.metadata["mutated"] = True
    assert edge_b.metadata == {}

    mapping_a = FieldMapping(source="f1", target="f2")
    mapping_b = FieldMapping(source="f2", target="f1")
    mapping_a.metadata["mutated"] = True
    assert mapping_b.metadata == {}


def test_edge_with_no_mappings_is_unchanged_from_prior_shape() -> None:
    """A mapping-less edge still has an empty `mappings` list and dumps as before DANDER-5."""
    edge = Edge(source="n1", target="n2", metadata={"note": "full-refresh"})
    assert edge.mappings == []
    dumped = edge.model_dump(by_alias=True)
    assert dumped == {
        "from": "n1",
        "to": "n2",
        "metadata": {"note": "full-refresh"},
        "mappings": [],
        "join": None,
    }


def test_field_mapping_on_disk_keys_are_source_and_target() -> None:
    """`FieldMapping` round-trips via validate/dump using the stable `source`/`target` keys."""
    mapping = FieldMapping.model_validate(
        {"source": "candidate_id", "target": "id", "metadata": {"note": "pk"}}
    )
    assert mapping.source == "candidate_id"
    assert mapping.target == "id"
    assert mapping.metadata == {"note": "pk"}

    dumped = mapping.model_dump()
    assert dumped == {
        "source": "candidate_id",
        "target": "id",
        "transformation": None,
        "metadata": {"note": "pk"},
    }


def test_edge_mappings_preserve_declaration_order(tmp_path: Path) -> None:
    """Multiple mappings on one edge preserve their declaration order, YAML and JSON alike."""
    yaml_path = tmp_path / "graph.yaml"
    yaml_path.write_text(_YAML_DOC)
    yaml_graph = load_graph_from_yaml(yaml_path)

    json_path = tmp_path / "graph.json"
    json_path.write_text(_JSON_DOC)
    json_graph = load_graph_from_json(json_path)

    for graph in (yaml_graph, json_graph):
        mappings = graph.edges[0].mappings
        assert [m.source for m in mappings] == ["candidate_id", "full_name"]
        assert [m.target for m in mappings] == ["candidate_id", "name"]


def test_dump_emits_stable_source_target_mapping_keys(tmp_path: Path) -> None:
    """Dumping an edge with mappings emits the `source`/`target` mapping keys on disk."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="task", name="a"), Node(id="n2", type="task", name="b")],
        edges=[
            Edge(
                source="n1",
                target="n2",
                mappings=[FieldMapping(source="f1", target="f2")],
            )
        ],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_text = yaml_path.read_text()
    assert "source: f1" in yaml_text
    assert "target: f2" in yaml_text
    # The edge itself still emits from/to, never source/target, at the edge level.
    assert "from: n1" in yaml_text
    assert "to: n2" in yaml_text

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_text = json_path.read_text()
    assert '"source": "f1"' in json_text
    assert '"target": "f2"' in json_text
    assert '"from": "n1"' in json_text
    assert '"to": "n2"' in json_text


def test_yaml_round_trip_is_stable(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph, including metadata/config, for YAML."""
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


def test_json_round_trip_is_stable(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph, including metadata/config, for JSON."""
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


def test_yaml_dump_emits_from_to_keys(tmp_path: Path) -> None:
    """Dumping to YAML serializes edges with `from`/`to` keys, matching the decided format."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="task", name="a"), Node(id="n2", type="task", name="b")],
        edges=[Edge(source="n1", target="n2")],
    )
    path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, path)
    text = path.read_text()
    assert "from: n1" in text
    assert "to: n2" in text
    assert "source:" not in text
    assert "target:" not in text


def test_json_dump_emits_from_to_keys(tmp_path: Path) -> None:
    """Dumping to JSON serializes edges with `from`/`to` keys, matching the decided format."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="task", name="a"), Node(id="n2", type="task", name="b")],
        edges=[Edge(source="n1", target="n2")],
    )
    path = tmp_path / "graph.json"
    dump_graph_to_json(graph, path)
    text = path.read_text()
    assert '"from"' in text
    assert '"to"' in text
    assert '"source"' not in text
    assert '"target"' not in text
