"""Unit tests for discriminated per-node-type config (DANDER-10).

Covers the typed `SourceNodeConfig`/`TransformNodeConfig`/`TargetNodeConfig` models, the
`resolve_node_config` routing seam, `Node`'s boundary validation that `config` matches its
declared `type`, round-trip stability through both YAML and JSON, and backward compatibility with
unmodeled types / the `params` alias / pre-existing DANDER-2-style graphs. No network; only
`tmp_path` I/O, matching `test_graph.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dander.pipeline.graph import (
    Edge,
    Node,
    PipelineGraph,
    dump_graph_to_json,
    dump_graph_to_yaml,
    load_graph_from_json,
    load_graph_from_yaml,
)
from dander.pipeline.node_config import (
    NodeConfig,
    SourceNodeConfig,
    TargetNodeConfig,
    TransformNodeConfig,
    resolve_node_config,
)

if TYPE_CHECKING:
    from pathlib import Path

_YAML_DOC = """
name: mixed_types
nodes:
  - id: n1
    type: source
    name: extract_candidates
    config:
      endpoint: /candidates
  - id: n2
    type: transform
    name: derive_full_name
    config:
      note: transform-extra
  - id: n3
    type: target
    name: load_candidates
    config:
      table: candidates
edges:
  - from: n1
    to: n2
  - from: n2
    to: n3
"""

_JSON_DOC = """
{
  "name": "mixed_types",
  "nodes": [
    {
      "id": "n1",
      "type": "source",
      "name": "extract_candidates",
      "config": {"endpoint": "/candidates"}
    },
    {
      "id": "n2",
      "type": "transform",
      "name": "derive_full_name",
      "config": {"note": "transform-extra"}
    },
    {
      "id": "n3",
      "type": "target",
      "name": "load_candidates",
      "config": {"table": "candidates"}
    }
  ],
  "edges": [
    {"from": "n1", "to": "n2"},
    {"from": "n2", "to": "n3"}
  ]
}
"""

_DANDER_2_YAML_DOC = """
name: candidate_ingest
nodes:
  - id: n1
    type: source
    name: extract_candidates
    config:
      endpoint: /candidates
      method: GET
  - id: n2
    type: target
    name: load_candidates
edges:
  - from: n1
    to: n2
"""


def _assert_mixed_types_graph(graph: PipelineGraph) -> None:
    source_node, transform_node, target_node = graph.nodes

    assert isinstance(source_node.config, SourceNodeConfig)
    assert source_node.config.endpoint == "/candidates"  # type: ignore[attr-defined]

    assert isinstance(transform_node.config, TransformNodeConfig)
    assert transform_node.config.note == "transform-extra"  # type: ignore[attr-defined]

    assert isinstance(target_node.config, TargetNodeConfig)
    assert target_node.config.table == "candidates"  # type: ignore[attr-defined]


def test_source_node_loads_typed_config_from_yaml(tmp_path: Path) -> None:
    """A `source` node's `config` loads as `SourceNodeConfig` from YAML, extra field preserved."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_mixed_types_graph(graph)


def test_source_node_loads_typed_config_from_json(tmp_path: Path) -> None:
    """A `source` node's `config` loads as `SourceNodeConfig` from JSON, extra field preserved."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_mixed_types_graph(graph)


def test_transform_node_loads_typed_config_from_yaml_and_json(tmp_path: Path) -> None:
    """A `transform` node's `config` loads as `TransformNodeConfig` in both formats."""
    yaml_path = tmp_path / "graph.yaml"
    yaml_path.write_text(_YAML_DOC)
    yaml_graph = load_graph_from_yaml(yaml_path)

    json_path = tmp_path / "graph.json"
    json_path.write_text(_JSON_DOC)
    json_graph = load_graph_from_json(json_path)

    for graph in (yaml_graph, json_graph):
        node = graph.nodes[1]
        assert isinstance(node.config, TransformNodeConfig)
        assert node.config.note == "transform-extra"  # type: ignore[attr-defined]


def test_target_node_loads_typed_config_from_yaml_and_json(tmp_path: Path) -> None:
    """A `target` node's `config` loads as `TargetNodeConfig` in both formats."""
    yaml_path = tmp_path / "graph.yaml"
    yaml_path.write_text(_YAML_DOC)
    yaml_graph = load_graph_from_yaml(yaml_path)

    json_path = tmp_path / "graph.json"
    json_path.write_text(_JSON_DOC)
    json_graph = load_graph_from_json(json_path)

    for graph in (yaml_graph, json_graph):
        node = graph.nodes[2]
        assert isinstance(node.config, TargetNodeConfig)
        assert node.config.table == "candidates"  # type: ignore[attr-defined]


def test_mismatched_typed_config_is_rejected_with_no_config_values() -> None:
    """A `source` node rejects a `TargetNodeConfig`-typed `config`, naming the mismatch only."""
    with pytest.raises(ValidationError) as exc_info:
        Node(id="n1", type="source", name="n", config=TargetNodeConfig(table="secret_table"))

    message = str(exc_info.value)
    assert "source" in message
    assert "SourceNodeConfig" in message
    assert "TargetNodeConfig" in message
    assert "secret_table" not in message


def test_mismatched_typed_config_is_rejected_in_reverse_direction() -> None:
    """A `target` node rejects a `SourceNodeConfig`-typed `config`, naming the mismatch only."""
    with pytest.raises(ValidationError) as exc_info:
        Node(id="n1", type="target", name="n", config=SourceNodeConfig(endpoint="/secret"))

    message = str(exc_info.value)
    assert "target" in message
    assert "TargetNodeConfig" in message
    assert "SourceNodeConfig" in message
    assert "/secret" not in message


def test_correctly_typed_config_instance_is_accepted() -> None:
    """A `config` instance whose concrete class matches its node's `type` is accepted as-is."""
    config = SourceNodeConfig(endpoint="/candidates")
    node = Node(id="n1", type="source", name="n", config=config)
    assert node.config == config
    assert isinstance(node.config, SourceNodeConfig)


def test_yaml_round_trip_is_stable_across_all_modeled_types(tmp_path: Path) -> None:
    """Load -> dump -> load is stable for a graph mixing source/transform/target configs (YAML)."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    loaded = load_graph_from_yaml(path)

    dump_path = tmp_path / "dumped.yaml"
    dump_graph_to_yaml(loaded, dump_path)
    reloaded = load_graph_from_yaml(dump_path)

    assert loaded == reloaded
    _assert_mixed_types_graph(reloaded)


def test_json_round_trip_is_stable_across_all_modeled_types(tmp_path: Path) -> None:
    """Load -> dump -> load is stable for a graph mixing source/transform/target configs (JSON)."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    loaded = load_graph_from_json(path)

    dump_path = tmp_path / "dumped.json"
    dump_graph_to_json(loaded, dump_path)
    reloaded = load_graph_from_json(dump_path)

    assert loaded == reloaded
    _assert_mixed_types_graph(reloaded)


def test_unmodeled_type_keeps_free_form_dict_config_and_round_trips(tmp_path: Path) -> None:
    """A node whose `type` has no stricter schema (e.g. `task`) keeps a plain dict `config`."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            Node(id="n1", type="task", name="a", config={"custom": "value"}),
            Node(id="n2", type="task", name="b"),
        ],
        edges=[Edge(source="n1", target="n2")],
    )
    assert graph.nodes[0].config == {"custom": "value"}
    assert not isinstance(graph.nodes[0].config, NodeConfig)
    assert graph.nodes[1].config == {}

    path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, path)
    reloaded = load_graph_from_yaml(path)
    assert reloaded == graph
    assert reloaded.nodes[0].config == {"custom": "value"}


def test_params_alias_still_populates_config() -> None:
    """The pre-existing `params` alias still populates `config`, routed through the typed model."""
    node = Node.model_validate(
        {"id": "n1", "type": "source", "name": "n", "params": {"endpoint": "/candidates"}}
    )
    assert isinstance(node.config, SourceNodeConfig)
    assert node.config.endpoint == "/candidates"  # type: ignore[attr-defined]


def test_modeled_node_with_no_config_loads_as_empty_typed_model_and_round_trips(
    tmp_path: Path,
) -> None:
    """A modeled node with no `config` key loads as an empty typed model and round-trips."""
    node = Node(id="n1", type="target", name="n")
    assert node.config == TargetNodeConfig()

    graph = PipelineGraph(
        name="g",
        nodes=[node, Node(id="n2", type="task", name="b")],
        edges=[Edge(source="n1", target="n2")],
    )
    path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, path)
    reloaded = load_graph_from_yaml(path)
    assert reloaded == graph
    assert reloaded.nodes[0].config == TargetNodeConfig()


def test_dander_2_style_graph_still_loads_and_round_trips(tmp_path: Path) -> None:
    """A pre-existing DANDER-2-style source->target graph still loads and round-trips equal."""
    path = tmp_path / "graph.yaml"
    path.write_text(_DANDER_2_YAML_DOC)
    loaded = load_graph_from_yaml(path)

    assert isinstance(loaded.nodes[0].config, SourceNodeConfig)
    assert loaded.nodes[0].config.endpoint == "/candidates"  # type: ignore[attr-defined]
    assert loaded.nodes[0].config.method == "GET"  # type: ignore[attr-defined]
    assert isinstance(loaded.nodes[1].config, TargetNodeConfig)

    dump_path = tmp_path / "dumped.yaml"
    dump_graph_to_yaml(loaded, dump_path)
    reloaded = load_graph_from_yaml(dump_path)
    assert loaded == reloaded


# -- resolve_node_config unit tests (the pure routing seam) -----------------------------------


def test_resolve_node_config_known_type_dict_returns_typed_instance() -> None:
    """A known type + dict value resolves to the matching typed instance."""
    result = resolve_node_config("source", {"endpoint": "/candidates"})
    assert isinstance(result, SourceNodeConfig)
    assert result.endpoint == "/candidates"  # type: ignore[attr-defined]


def test_resolve_node_config_known_type_correct_instance_returns_same_instance() -> None:
    """A known type + an already-correct typed instance is returned unchanged."""
    config = SourceNodeConfig(endpoint="/candidates")
    result = resolve_node_config("source", config)
    assert result is config


def test_resolve_node_config_known_type_wrong_instance_raises() -> None:
    """A known type + a wrong typed instance raises `ValueError` naming the mismatch."""
    with pytest.raises(ValueError, match="source.*SourceNodeConfig.*TargetNodeConfig"):
        resolve_node_config("source", TargetNodeConfig())


def test_resolve_node_config_unmodeled_type_dict_returns_same_dict() -> None:
    """An unmodeled type + dict value passes through unchanged."""
    value = {"custom": "value"}
    result = resolve_node_config("task", value)
    assert result == value
    assert not isinstance(result, NodeConfig)


def test_resolve_node_config_handles_none_and_absent() -> None:
    """`None` resolves to an empty typed model for a known type, and `{}` for an unmodeled one."""
    known = resolve_node_config("target", None)
    assert known == TargetNodeConfig()

    unmodeled = resolve_node_config("task", None)
    assert unmodeled == {}
