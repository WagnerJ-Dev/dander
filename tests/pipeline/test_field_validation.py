"""Unit tests for `dander.pipeline.graph_ops.validate_field_wiring` (DANDER-8).

Covers field-wiring validation: field names unique within a node, mapping source/target field
references resolve, transformation input references resolve, and join key field references
resolve — plus the documented ordering contract (structural validation, DANDER-3, surfaces before
any field-wiring error). Pure in-memory `PipelineGraph` objects; no network, no mocks. Fixtures use
synthetic field/type names only, never real data (`steering/01-security.md`).
"""

from __future__ import annotations

import pytest

from dander.pipeline.errors import (
    DuplicateFieldNameError,
    DuplicateNodeIdError,
    FieldReferenceKind,
    JoinKeyFieldError,
    UnknownFieldReferenceError,
)
from dander.pipeline.graph import (
    Edge,
    FieldMapping,
    JoinKeyPair,
    JoinSpec,
    JoinType,
    Node,
    NodeField,
    PipelineGraph,
    Transformation,
    TransformationKind,
)
from dander.pipeline.graph_ops import validate_field_wiring


def _node(node_id: str, field_names: list[str] | None = None) -> Node:
    fields = [NodeField(name=name, type="STRING") for name in (field_names or [])]
    return Node(id=node_id, type="task", name=node_id, fields=fields)


def _edge(
    source: str,
    target: str,
    *,
    mappings: list[FieldMapping] | None = None,
    join: JoinSpec | None = None,
) -> Edge:
    return Edge(source=source, target=target, mappings=mappings or [], join=join)


def test_fully_wired_valid_graph_passes_without_raising() -> None:
    """A graph whose mappings, transformation inputs, and join keys all resolve validates."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            _node("src", ["candidate_id", "first_name", "last_name"]),
            _node("stg", ["candidate_id", "full_name"]),
            _node("dim", ["candidate_id", "region"]),
        ],
        edges=[
            _edge(
                "src",
                "stg",
                mappings=[
                    FieldMapping(source="candidate_id", target="candidate_id"),
                    FieldMapping(
                        source="first_name",
                        target="full_name",
                        transformation=Transformation(
                            kind=TransformationKind.EXPRESSION,
                            expression="CONCAT(first_name, ' ', last_name)",
                            inputs=["first_name", "last_name"],
                        ),
                    ),
                ],
            ),
            _edge(
                "src",
                "dim",
                join=JoinSpec(
                    type=JoinType.INNER,
                    keys=[JoinKeyPair(left="candidate_id", right="candidate_id")],
                ),
            ),
        ],
    )
    validate_field_wiring(graph)  # should not raise


def test_duplicate_field_name_raises_with_offending_node_and_field() -> None:
    """Two fields on one node sharing a name raise `DuplicateFieldNameError` naming both."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("n1", ["email", "email"])],
        edges=[],
    )
    with pytest.raises(DuplicateFieldNameError) as exc_info:
        validate_field_wiring(graph)
    assert exc_info.value.node_id == "n1"
    assert exc_info.value.field_name == "email"
    assert "email" in str(exc_info.value)
    assert "n1" in str(exc_info.value)


def test_mapping_missing_source_field_raises() -> None:
    """A `FieldMapping.source` not declared on the edge's source node raises with the right kind."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("src", ["candidate_id"]), _node("stg", ["candidate_id"])],
        edges=[_edge("src", "stg", mappings=[FieldMapping(source="emial", target="candidate_id")])],
    )
    with pytest.raises(UnknownFieldReferenceError) as exc_info:
        validate_field_wiring(graph)
    err = exc_info.value
    assert err.node_id == "src"
    assert err.field_name == "emial"
    assert err.edge == ("src", "stg")
    assert err.reference_kind is FieldReferenceKind.MAPPING_SOURCE
    assert "emial" in str(err)
    assert "src" in str(err)


def test_mapping_missing_target_field_raises() -> None:
    """A `FieldMapping.target` not declared on the edge's target node raises with the right kind."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("src", ["candidate_id"]), _node("stg", ["candidate_id"])],
        edges=[
            _edge("src", "stg", mappings=[FieldMapping(source="candidate_id", target="cand_id")])
        ],
    )
    with pytest.raises(UnknownFieldReferenceError) as exc_info:
        validate_field_wiring(graph)
    err = exc_info.value
    assert err.node_id == "stg"
    assert err.field_name == "cand_id"
    assert err.edge == ("src", "stg")
    assert err.reference_kind is FieldReferenceKind.MAPPING_TARGET
    assert "cand_id" in str(err)


def test_transformation_input_missing_field_raises() -> None:
    """A transformation input field not declared on the edge's source node raises."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("src", ["first_name"]), _node("stg", ["full_name"])],
        edges=[
            _edge(
                "src",
                "stg",
                mappings=[
                    FieldMapping(
                        source="first_name",
                        target="full_name",
                        transformation=Transformation(
                            kind=TransformationKind.EXPRESSION,
                            expression="CONCAT(first_name, ' ', last_name)",
                            inputs=["first_name", "last_name"],
                        ),
                    )
                ],
            )
        ],
    )
    with pytest.raises(UnknownFieldReferenceError) as exc_info:
        validate_field_wiring(graph)
    err = exc_info.value
    assert err.node_id == "src"
    assert err.field_name == "last_name"
    assert err.edge == ("src", "stg")
    assert err.reference_kind is FieldReferenceKind.TRANSFORMATION_INPUT
    assert "last_name" in str(err)


def test_transformation_with_no_inputs_is_a_no_op() -> None:
    """A zero-input transformation (e.g. `constant`) raises nothing, regardless of fields."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("src", []), _node("stg", ["status"])],
        edges=[
            _edge(
                "src",
                "stg",
                mappings=[
                    FieldMapping(
                        target="status",
                        transformation=Transformation(
                            kind=TransformationKind.CONSTANT, constant="active"
                        ),
                    )
                ],
            )
        ],
    )
    validate_field_wiring(graph)  # should not raise


def test_join_key_missing_on_left_node_raises_join_key_field_error() -> None:
    """A join key's `left` field missing on the edge's source node raises `JoinKeyFieldError`."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("src", []), _node("dim", ["candidate_id"])],
        edges=[
            _edge(
                "src",
                "dim",
                join=JoinSpec(
                    type=JoinType.INNER,
                    keys=[JoinKeyPair(left="candidate_id", right="candidate_id")],
                ),
            )
        ],
    )
    with pytest.raises(JoinKeyFieldError) as exc_info:
        validate_field_wiring(graph)
    err = exc_info.value
    assert err.node_id == "src"
    assert err.field_name == "candidate_id"
    assert err.edge == ("src", "dim")
    assert err.reference_kind is FieldReferenceKind.JOIN_LEFT
    assert err.key_index == 0
    # A JoinKeyFieldError is also catchable as the more general UnknownFieldReferenceError.
    assert isinstance(err, UnknownFieldReferenceError)


def test_join_key_missing_on_right_node_raises_join_key_field_error() -> None:
    """A join key's `right` field missing on the edge's target node raises `JoinKeyFieldError`."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("src", ["candidate_id"]), _node("dim", [])],
        edges=[
            _edge(
                "src",
                "dim",
                join=JoinSpec(
                    type=JoinType.INNER,
                    keys=[JoinKeyPair(left="candidate_id", right="candidate_id")],
                ),
            )
        ],
    )
    with pytest.raises(JoinKeyFieldError) as exc_info:
        validate_field_wiring(graph)
    err = exc_info.value
    assert err.node_id == "dim"
    assert err.field_name == "candidate_id"
    assert err.edge == ("src", "dim")
    assert err.reference_kind is FieldReferenceKind.JOIN_RIGHT
    assert isinstance(err, UnknownFieldReferenceError)


def test_second_join_key_pair_reports_correct_index() -> None:
    """A failure on the second key pair reports `key_index == 1`, not the first."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("src", ["candidate_id", "req_id"]), _node("dim", ["candidate_id"])],
        edges=[
            _edge(
                "src",
                "dim",
                join=JoinSpec(
                    type=JoinType.INNER,
                    keys=[
                        JoinKeyPair(left="candidate_id", right="candidate_id"),
                        JoinKeyPair(left="req_id", right="requisition_id"),
                    ],
                ),
            )
        ],
    )
    with pytest.raises(JoinKeyFieldError) as exc_info:
        validate_field_wiring(graph)
    assert exc_info.value.key_index == 1
    assert exc_info.value.reference_kind is FieldReferenceKind.JOIN_RIGHT


def test_structural_error_surfaces_before_field_wiring_error() -> None:
    """A graph with both a structural fault and a field-wiring fault raises the structural error."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("n1", []), _node("n1", [])],  # duplicate node id: structural fault
        edges=[
            _edge("n1", "n1", mappings=[FieldMapping(source="ghost", target="also_ghost")]),
        ],
    )
    with pytest.raises(DuplicateNodeIdError):
        validate_field_wiring(graph)


def test_no_message_leaks_metadata_config_or_transformation_payload() -> None:
    """Error messages never include field/edge metadata, node config, or transformation payloads."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            Node(
                id="src",
                type="source",
                name="src",
                config={"api_key_ref": "projects/p/secrets/sf/versions/latest"},
                fields=[],
            ),
            _node("stg", ["full_name"]),
        ],
        edges=[
            _edge(
                "src",
                "stg",
                mappings=[
                    FieldMapping(
                        target="full_name",
                        transformation=Transformation(
                            kind=TransformationKind.EXPRESSION,
                            expression="SECRET_LOOKING_EXPRESSION('should-not-leak')",
                            inputs=["missing_input"],
                        ),
                        metadata={"note": "sensitive-note-should-not-leak"},
                    )
                ],
            )
        ],
    )
    with pytest.raises(UnknownFieldReferenceError) as exc_info:
        validate_field_wiring(graph)
    message = str(exc_info.value)
    assert "api_key_ref" not in message
    assert "projects/p/secrets" not in message
    assert "SECRET_LOOKING_EXPRESSION" not in message
    assert "sensitive-note-should-not-leak" not in message
