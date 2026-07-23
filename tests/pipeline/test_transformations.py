"""Unit tests for `Transformation`/`TransformationKind` and their effect on `FieldMapping`.

Covers DANDER-6: a mapping's `direct`/`expression`/`constant` transformation loads and round-trips
through both YAML and JSON, input-field references survive the round-trip, and the intra-model
boundary constraints reject malformed transformations. Fixtures use benign, synthetic logic only
(e.g. `CONCAT(first_name, ' ', last_name)`, constant `"active"`) — never a secret or real data,
per `steering/01-security.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dander.pipeline.graph import (
    Edge,
    FieldMapping,
    Node,
    PipelineGraph,
    Transformation,
    TransformationKind,
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
    type: target
    name: load_candidates
edges:
  - from: n1
    to: n2
    mappings:
      - source: candidate_id
        target: candidate_id
      - source: first_name
        target: full_name
        transformation:
          kind: expression
          expression: "CONCAT(first_name, ' ', last_name)"
          inputs: [first_name, last_name]
      - target: status
        transformation:
          kind: constant
          constant: active
"""

_JSON_DOC = """
{
  "name": "candidate_ingest",
  "nodes": [
    {"id": "n1", "type": "source", "name": "extract_candidates"},
    {"id": "n2", "type": "target", "name": "load_candidates"}
  ],
  "edges": [
    {
      "from": "n1",
      "to": "n2",
      "mappings": [
        {"source": "candidate_id", "target": "candidate_id"},
        {
          "source": "first_name",
          "target": "full_name",
          "transformation": {
            "kind": "expression",
            "expression": "CONCAT(first_name, ' ', last_name)",
            "inputs": ["first_name", "last_name"]
          }
        },
        {
          "target": "status",
          "transformation": {"kind": "constant", "constant": "active"}
        }
      ]
    }
  ]
}
"""


def _assert_expected_graph(graph: PipelineGraph) -> None:
    mappings = graph.edges[0].mappings
    assert len(mappings) == 3

    direct = mappings[0]
    assert direct.source == "candidate_id"
    assert direct.target == "candidate_id"
    assert direct.transformation is None

    expr = mappings[1]
    assert expr.source == "first_name"
    assert expr.target == "full_name"
    assert expr.transformation is not None
    assert expr.transformation.kind is TransformationKind.EXPRESSION
    assert expr.transformation.expression == "CONCAT(first_name, ' ', last_name)"
    assert expr.transformation.inputs == ["first_name", "last_name"]
    assert expr.transformation.constant is None

    const = mappings[2]
    assert const.source is None
    assert const.target == "status"
    assert const.transformation is not None
    assert const.transformation.kind is TransformationKind.CONSTANT
    assert const.transformation.constant == "active"
    assert const.transformation.expression is None


def test_mapping_loads_direct_expression_and_constant_from_yaml(tmp_path: Path) -> None:
    """A `direct`, an `expression`, and a `constant` transformation load correctly from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_expected_graph(graph)


def test_mapping_loads_direct_expression_and_constant_from_json(tmp_path: Path) -> None:
    """A `direct`, an `expression`, and a `constant` transformation load correctly from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_expected_graph(graph)


def test_yaml_round_trip_is_stable_with_transformations(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for YAML, all three kinds included."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    loaded = load_graph_from_yaml(path)

    dump_path = tmp_path / "dumped.yaml"
    dump_graph_to_yaml(loaded, dump_path)
    reloaded = load_graph_from_yaml(dump_path)

    assert loaded == reloaded
    assert reloaded.edges[0].mappings[1].transformation is not None
    assert reloaded.edges[0].mappings[1].transformation.inputs == ["first_name", "last_name"]


def test_json_round_trip_is_stable_with_transformations(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for JSON, all three kinds included."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    loaded = load_graph_from_json(path)

    dump_path = tmp_path / "dumped.json"
    dump_graph_to_json(loaded, dump_path)
    reloaded = load_graph_from_json(dump_path)

    assert loaded == reloaded
    assert reloaded.edges[0].mappings[1].transformation is not None
    assert reloaded.edges[0].mappings[1].transformation.inputs == ["first_name", "last_name"]


def test_mapping_with_no_transformation_round_trips_unchanged(tmp_path: Path) -> None:
    """A plain DANDER-5 direct mapping with no `transformation` still round-trips, both formats."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="task", name="a"), Node(id="n2", type="task", name="b")],
        edges=[Edge(source="n1", target="n2", mappings=[FieldMapping(source="f1", target="f2")])],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    reloaded_yaml = load_graph_from_yaml(yaml_path)
    assert graph == reloaded_yaml
    assert reloaded_yaml.edges[0].mappings[0].transformation is None

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    reloaded_json = load_graph_from_json(json_path)
    assert graph == reloaded_json
    assert reloaded_json.edges[0].mappings[0].transformation is None


def test_explicit_direct_transformation_is_legal_and_round_trips(tmp_path: Path) -> None:
    """An explicit `Transformation(kind=DIRECT)` is accepted and round-trips like `None`."""
    mapping = FieldMapping(
        source="f1", target="f2", transformation=Transformation(kind=TransformationKind.DIRECT)
    )
    assert mapping.transformation is not None
    assert mapping.transformation.kind is TransformationKind.DIRECT

    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="task", name="a"), Node(id="n2", type="task", name="b")],
        edges=[Edge(source="n1", target="n2", mappings=[mapping])],
    )
    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    reloaded = load_graph_from_yaml(yaml_path)
    assert reloaded == graph


def test_expression_kind_rejects_empty_expression() -> None:
    """`EXPRESSION` kind with an empty/whitespace expression raises `ValidationError`."""
    with pytest.raises(ValidationError):
        Transformation(kind=TransformationKind.EXPRESSION, expression="   ")


def test_expression_kind_rejects_missing_expression() -> None:
    """`EXPRESSION` kind with no `expression` at all raises `ValidationError`."""
    with pytest.raises(ValidationError):
        Transformation(kind=TransformationKind.EXPRESSION)


def test_expression_kind_rejects_constant_set() -> None:
    """`EXPRESSION` kind with `constant` also set raises `ValidationError`."""
    with pytest.raises(ValidationError):
        Transformation(kind=TransformationKind.EXPRESSION, expression="UPPER(x)", constant="y")


def test_constant_kind_rejects_missing_constant() -> None:
    """`CONSTANT` kind with no `constant` literal provided raises `ValidationError`."""
    with pytest.raises(ValidationError):
        Transformation(kind=TransformationKind.CONSTANT)


def test_constant_kind_accepts_explicit_null_literal() -> None:
    """`CONSTANT` kind with an explicit `constant: null` is legal (presence, not truthiness)."""
    transformation = Transformation(kind=TransformationKind.CONSTANT, constant=None)
    assert transformation.constant is None


def _graph_with_null_constant() -> PipelineGraph:
    return PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="source", name="a"), Node(id="n2", type="target", name="b")],
        edges=[
            Edge(
                source="n1",
                target="n2",
                mappings=[
                    FieldMapping(
                        target="flag",
                        transformation=Transformation(
                            kind=TransformationKind.CONSTANT, constant=None
                        ),
                    )
                ],
            )
        ],
    )


def test_constant_null_round_trips_through_dump_graph_to_yaml(tmp_path: Path) -> None:
    """A `CONSTANT` transformation with `constant=None` survives dump-and-reload via YAML.

    Regression test for a prior graph-wide `exclude_none=True` on `dump_graph_to_yaml`, which
    silently dropped an authored `constant: null` on dump; on reload the `CONSTANT`-kind
    validator then raised `ValidationError` since `constant` was no longer "set" (see
    `Transformation._check_kind_payload`). Only a join-less edge's `join` key may be omitted on
    dump; a meaningful `constant: null` must not be.
    """
    graph = _graph_with_null_constant()
    path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, path)
    reloaded = load_graph_from_yaml(path)
    assert reloaded == graph


def test_constant_null_round_trips_through_dump_graph_to_json(tmp_path: Path) -> None:
    """A `CONSTANT` transformation with `constant=None` survives dump-and-reload via JSON.

    Regression test for a prior graph-wide `exclude_none=True` on `dump_graph_to_json`, which
    silently dropped an authored `constant: null` on dump; on reload the `CONSTANT`-kind
    validator then raised `ValidationError` since `constant` was no longer "set" (see
    `Transformation._check_kind_payload`). Only a join-less edge's `join` key may be omitted on
    dump; a meaningful `constant: null` must not be.
    """
    graph = _graph_with_null_constant()
    path = tmp_path / "graph.json"
    dump_graph_to_json(graph, path)
    reloaded = load_graph_from_json(path)
    assert reloaded == graph


def test_constant_kind_rejects_expression_set() -> None:
    """`CONSTANT` kind with `expression` also set raises `ValidationError`."""
    with pytest.raises(ValidationError):
        Transformation(kind=TransformationKind.CONSTANT, constant="active", expression="UPPER(x)")


def test_direct_kind_rejects_expression_or_constant() -> None:
    """`DIRECT` kind (the default) rejects a set `expression` or `constant`."""
    with pytest.raises(ValidationError):
        Transformation(kind=TransformationKind.DIRECT, expression="UPPER(x)")
    with pytest.raises(ValidationError):
        Transformation(kind=TransformationKind.DIRECT, constant="active")


def test_derived_mapping_without_source_requires_transformation() -> None:
    """A mapping with `source=None` and no `transformation` raises `ValidationError`."""
    with pytest.raises(ValidationError):
        FieldMapping(target="status")


def test_derived_mapping_without_source_rejects_direct_transformation() -> None:
    """A mapping with `source=None` and a `DIRECT` transformation still raises `ValidationError`."""
    with pytest.raises(ValidationError):
        FieldMapping(target="status", transformation=Transformation(kind=TransformationKind.DIRECT))


def test_derived_mapping_without_source_accepts_expression_transformation() -> None:
    """A mapping with `source=None` and an `EXPRESSION` transformation is valid."""
    mapping = FieldMapping(
        target="full_name",
        transformation=Transformation(
            kind=TransformationKind.EXPRESSION,
            expression="CONCAT(first_name, ' ', last_name)",
            inputs=["first_name", "last_name"],
        ),
    )
    assert mapping.source is None
    assert mapping.transformation is not None
    assert mapping.transformation.inputs == ["first_name", "last_name"]


def test_derived_mapping_without_source_accepts_constant_transformation() -> None:
    """A mapping with `source=None` and a `CONSTANT` transformation is valid."""
    mapping = FieldMapping(
        target="status",
        transformation=Transformation(kind=TransformationKind.CONSTANT, constant="active"),
    )
    assert mapping.source is None
    assert mapping.transformation is not None
    assert mapping.transformation.constant == "active"
