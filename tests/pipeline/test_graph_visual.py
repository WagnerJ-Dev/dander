"""Unit tests for ``Position``/``NodeVisual`` and `Node.visual` (DANDER-19).

Covers a node's optional presentation/layout metadata for the future drag-drop UI named in
`dander.pipeline.graph`'s module docstring: loading from YAML and JSON, stable round-trip through
both formats (including a partially-populated `NodeVisual`), backward compatibility of a
visual-less node (unchanged dump, no `visual` key emitted), and a mixed-node graph round-trip. No
data/execution semantics are exercised anywhere in this suite — model + serialization only,
matching the rest of `dander.pipeline.graph`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dander.pipeline.graph import (
    Node,
    NodeVisual,
    PipelineGraph,
    Position,
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
    visual:
      position:
        x: 100
        y: 200.5
      color: "#3366cc"
      icon: database
edges: []
"""

_JSON_DOC = """
{
  "name": "candidate_ingest",
  "nodes": [
    {
      "id": "n1",
      "type": "source",
      "name": "extract_candidates",
      "visual": {
        "position": {"x": 100, "y": 200.5},
        "color": "#3366cc",
        "icon": "database"
      }
    }
  ],
  "edges": []
}
"""


def test_node_loads_visual_metadata_from_yaml(tmp_path: Path) -> None:
    """A node loads `visual` (position + color + icon) from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)

    node = graph.nodes[0]
    assert node.visual is not None
    assert node.visual.position == Position(x=100, y=200.5)
    assert node.visual.color == "#3366cc"
    assert node.visual.icon == "database"


def test_node_loads_visual_metadata_from_json(tmp_path: Path) -> None:
    """A node loads `visual` (position + color + icon) from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)

    node = graph.nodes[0]
    assert node.visual is not None
    assert node.visual.position == Position(x=100, y=200.5)
    assert node.visual.color == "#3366cc"
    assert node.visual.icon == "database"


def test_yaml_round_trip_is_stable_with_visual(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for YAML, including visual metadata."""
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


def test_json_round_trip_is_stable_with_visual(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for JSON, including visual metadata."""
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


def test_round_trip_stable_with_color_and_icon_only_no_position(tmp_path: Path) -> None:
    """A `NodeVisual` with only color/icon (no position) round-trips equal, both formats."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            Node(
                id="n1",
                type="source",
                name="a",
                visual=NodeVisual(color="#112233", icon="table"),
            )
        ],
        edges=[],
    )
    assert graph.nodes[0].visual is not None
    assert graph.nodes[0].visual.position is None

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    reloaded_yaml = load_graph_from_yaml(yaml_path)
    assert reloaded_yaml == graph
    assert reloaded_yaml.nodes[0].visual is not None
    assert reloaded_yaml.nodes[0].visual.position is None

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    reloaded_json = load_graph_from_json(json_path)
    assert reloaded_json == graph
    assert reloaded_json.nodes[0].visual is not None
    assert reloaded_json.nodes[0].visual.position is None


def test_round_trip_stable_with_position_only_no_color_or_icon(tmp_path: Path) -> None:
    """A `NodeVisual` with only a position (no color/icon) round-trips equal, both formats."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            Node(
                id="n1",
                type="source",
                name="a",
                visual=NodeVisual(position=Position(x=1.5, y=2.5)),
            )
        ],
        edges=[],
    )
    assert graph.nodes[0].visual is not None
    assert graph.nodes[0].visual.color is None
    assert graph.nodes[0].visual.icon is None

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    reloaded_yaml = load_graph_from_yaml(yaml_path)
    assert reloaded_yaml == graph

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    reloaded_json = load_graph_from_json(json_path)
    assert reloaded_json == graph


def test_visual_less_node_round_trips_unchanged_and_omits_visual_key(tmp_path: Path) -> None:
    """A visual-less node round-trips equal and its dumped text carries no `visual` key."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="source", name="a")],
        edges=[],
    )
    assert graph.nodes[0].visual is None

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_text = yaml_path.read_text()
    assert "visual" not in yaml_text
    reloaded_yaml = load_graph_from_yaml(yaml_path)
    assert reloaded_yaml == graph
    assert reloaded_yaml.nodes[0].visual is None

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_text = json_path.read_text()
    assert "visual" not in json_text
    reloaded_json = load_graph_from_json(json_path)
    assert reloaded_json == graph
    assert reloaded_json.nodes[0].visual is None


def test_node_with_visual_dumps_nested_visual_block(tmp_path: Path) -> None:
    """A node with visual metadata dumps a nested `visual` block, both formats."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            Node(
                id="n1",
                type="source",
                name="a",
                visual=NodeVisual(position=Position(x=10, y=20), color="#3366cc", icon="database"),
            )
        ],
        edges=[],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_text = yaml_path.read_text()
    assert "visual:" in yaml_text
    assert "color: '#3366cc'" in yaml_text
    assert "icon: database" in yaml_text

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_text = json_path.read_text()
    assert '"visual"' in json_text
    assert '"color": "#3366cc"' in json_text
    assert '"icon": "database"' in json_text


def test_graph_mixing_visual_and_visual_less_nodes_round_trips(tmp_path: Path) -> None:
    """A graph mixing a visual and a visual-less node round-trips with equality preserved."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            Node(
                id="n1",
                type="source",
                name="a",
                visual=NodeVisual(position=Position(x=0, y=0), color="#3366cc", icon="database"),
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
