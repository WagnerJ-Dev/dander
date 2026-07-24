"""Unit tests for ``CursorKind``/``CursorStrategy`` and `Node.cursor` (DANDER-18).

Covers a node's optional declarative watermark/cursor strategy: intra-model boundary constraints
(non-empty `field`, closed `kind` set), loading each `CursorKind` from YAML and JSON, stable
round-trip through both formats, backward compatibility of a cursor-less node (unchanged dump, no
`cursor` key emitted), direct construction, and the `from_incremental_cursor` migration helper. No
state is read, written, or persisted anywhere in this suite — model + serialization only, matching
the rest of `dander.pipeline.graph`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dander.pipeline.graph import (
    CursorKind,
    CursorStrategy,
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
    cursor:
      field: updated_at
      kind: timestamp
      metadata:
        note: from-yaml
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
      "cursor": {
        "field": "updated_at",
        "kind": "timestamp",
        "metadata": {"note": "from-json"}
      }
    }
  ],
  "edges": []
}
"""


def _yaml_doc_for_kind(kind: str, field: str) -> str:
    return f"""
name: candidate_ingest
nodes:
  - id: n1
    type: source
    name: extract_candidates
    cursor:
      field: {field}
      kind: {kind}
      params:
        hint: sample
edges: []
"""


def _json_doc_for_kind(kind: str, field: str) -> str:
    return f"""
{{
  "name": "candidate_ingest",
  "nodes": [
    {{
      "id": "n1",
      "type": "source",
      "name": "extract_candidates",
      "cursor": {{
        "field": "{field}",
        "kind": "{kind}",
        "params": {{"hint": "sample"}}
      }}
    }}
  ],
  "edges": []
}}
"""


@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("timestamp", "updated_at"),
        ("sequence", "row_seq"),
        ("opaque_token", "next_token"),
    ],
)
def test_node_loads_cursor_strategy_for_each_kind_from_yaml(
    tmp_path: Path, kind: str, field: str
) -> None:
    """A node loads a `CursorStrategy` for each `CursorKind` from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_yaml_doc_for_kind(kind, field))
    graph = load_graph_from_yaml(path)

    node = graph.nodes[0]
    assert node.cursor is not None
    assert node.cursor.field == field
    assert node.cursor.kind is CursorKind(kind)
    assert node.cursor.params == {"hint": "sample"}
    assert node.cursor.metadata == {}


@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("timestamp", "updated_at"),
        ("sequence", "row_seq"),
        ("opaque_token", "next_token"),
    ],
)
def test_node_loads_cursor_strategy_for_each_kind_from_json(
    tmp_path: Path, kind: str, field: str
) -> None:
    """A node loads a `CursorStrategy` for each `CursorKind` from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_json_doc_for_kind(kind, field))
    graph = load_graph_from_json(path)

    node = graph.nodes[0]
    assert node.cursor is not None
    assert node.cursor.field == field
    assert node.cursor.kind is CursorKind(kind)
    assert node.cursor.params == {"hint": "sample"}
    assert node.cursor.metadata == {}


def test_node_loads_cursor_strategy_from_yaml_with_metadata(tmp_path: Path) -> None:
    """A node loads a `CursorStrategy` (field/kind/metadata) from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)

    node = graph.nodes[0]
    assert node.cursor is not None
    assert node.cursor.field == "updated_at"
    assert node.cursor.kind is CursorKind.TIMESTAMP
    assert node.cursor.metadata == {"note": "from-yaml"}


def test_node_loads_cursor_strategy_from_json_with_metadata(tmp_path: Path) -> None:
    """A node loads a `CursorStrategy` (field/kind/metadata) from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)

    node = graph.nodes[0]
    assert node.cursor is not None
    assert node.cursor.field == "updated_at"
    assert node.cursor.kind is CursorKind.TIMESTAMP
    assert node.cursor.metadata == {"note": "from-json"}


def test_cursor_strategy_rejects_empty_field() -> None:
    """A `CursorStrategy` with an empty `field` raises `ValidationError`."""
    with pytest.raises(ValidationError):
        CursorStrategy(field="", kind=CursorKind.TIMESTAMP)


def test_cursor_strategy_rejects_whitespace_only_field() -> None:
    """A `CursorStrategy` with a whitespace-only `field` raises `ValidationError`."""
    with pytest.raises(ValidationError):
        CursorStrategy(field="   ", kind=CursorKind.SEQUENCE)


def test_cursor_strategy_rejects_invalid_kind() -> None:
    """An unrecognized cursor `kind` raises a `ValidationError` at the Pydantic boundary."""
    with pytest.raises(ValidationError):
        CursorStrategy.model_validate({"field": "updated_at", "kind": "polling_interval"})


def test_cursor_strategy_constructs_directly() -> None:
    """`CursorStrategy` constructs directly with attribute names, not just on-disk keys."""
    strategy = CursorStrategy(field="row_seq", kind=CursorKind.SEQUENCE, params={"step": 1})
    assert strategy.field == "row_seq"
    assert strategy.kind is CursorKind.SEQUENCE
    assert strategy.params == {"step": 1}
    assert strategy.metadata == {}


def test_yaml_round_trip_is_stable_with_cursor(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for YAML, including cursor metadata."""
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


def test_json_round_trip_is_stable_with_cursor(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for JSON, including cursor metadata."""
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


def test_cursor_less_node_round_trips_unchanged_and_omits_cursor_key(tmp_path: Path) -> None:
    """A cursor-less node round-trips equal and its dumped text carries no `cursor` key."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="source", name="a")],
        edges=[],
    )
    assert graph.nodes[0].cursor is None

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_text = yaml_path.read_text()
    assert "cursor" not in yaml_text
    reloaded_yaml = load_graph_from_yaml(yaml_path)
    assert reloaded_yaml == graph
    assert reloaded_yaml.nodes[0].cursor is None

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_text = json_path.read_text()
    assert "cursor" not in json_text
    reloaded_json = load_graph_from_json(json_path)
    assert reloaded_json == graph
    assert reloaded_json.nodes[0].cursor is None


def test_node_with_cursor_dumps_nested_cursor_block(tmp_path: Path) -> None:
    """A node with a cursor dumps a nested `cursor` block with `field`/`kind`, both formats."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            Node(
                id="n1",
                type="source",
                name="a",
                cursor=CursorStrategy(field="row_seq", kind=CursorKind.SEQUENCE),
            )
        ],
        edges=[],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_text = yaml_path.read_text()
    assert "cursor:" in yaml_text
    assert "field: row_seq" in yaml_text
    assert "kind: sequence" in yaml_text

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_text = json_path.read_text()
    assert '"cursor"' in json_text
    assert '"field": "row_seq"' in json_text
    assert '"kind": "sequence"' in json_text


def test_from_incremental_cursor_returns_none_for_none() -> None:
    """`from_incremental_cursor(None)` returns `None`."""
    assert CursorStrategy.from_incremental_cursor(None) is None


def test_from_incremental_cursor_returns_none_for_empty_string() -> None:
    """`from_incremental_cursor("")` returns `None`."""
    assert CursorStrategy.from_incremental_cursor("") is None


def test_from_incremental_cursor_maps_to_timestamp_strategy() -> None:
    """`from_incremental_cursor("updated_at")` maps to a `TIMESTAMP`-kind `CursorStrategy`."""
    strategy = CursorStrategy.from_incremental_cursor("updated_at")
    assert strategy == CursorStrategy(field="updated_at", kind=CursorKind.TIMESTAMP)
