"""Unit tests for `NodeField` casting overrides (`cast_to`) and generic tests (`FieldTest`).

Covers DANDER-17: a field's `cast_to` (raw-vs-target casting override) and `tests` (declarative
`not_null`/`unique`/`accepted_values`/`relationships` generic tests) load and round-trip through
both YAML and JSON, boundary constraints reject malformed tests, and a plain DANDER-4 field
(no `cast_to`/`tests`) is unaffected. Fixtures use synthetic type/token names only (e.g.
`cast_to: DATE`, `values: [active, inactive]`) -- never a real field value or sample datum, per
`steering/01-security.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dander.pipeline.graph import (
    FieldTest,
    GenericTestKind,
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
    fields:
      - name: applied_at
        type: STRING
        cast_to: TIMESTAMP
        tests:
          - kind: not_null
          - kind: unique
          - kind: accepted_values
            values: [applied, withdrawn, hired]
          - kind: relationships
            to: n2
            field: candidate_id
      - name: candidate_id
        type: STRING
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
      "fields": [
        {
          "name": "applied_at",
          "type": "STRING",
          "cast_to": "TIMESTAMP",
          "tests": [
            {"kind": "not_null"},
            {"kind": "unique"},
            {"kind": "accepted_values", "values": ["applied", "withdrawn", "hired"]},
            {"kind": "relationships", "to": "n2", "field": "candidate_id"}
          ]
        },
        {"name": "candidate_id", "type": "STRING"}
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
    node = graph.nodes[0]
    assert node.id == "n1"
    assert len(node.fields) == 2

    applied_at = node.fields[0]
    assert applied_at.name == "applied_at"
    assert applied_at.type == "STRING"
    assert applied_at.cast_to == "TIMESTAMP"
    assert len(applied_at.tests) == 4

    not_null, unique, accepted_values, relationships = applied_at.tests

    assert not_null.kind is GenericTestKind.NOT_NULL
    assert not_null.values == []
    assert not_null.to is None
    assert not_null.field is None

    assert unique.kind is GenericTestKind.UNIQUE
    assert unique.values == []

    assert accepted_values.kind is GenericTestKind.ACCEPTED_VALUES
    assert accepted_values.values == ["applied", "withdrawn", "hired"]
    assert accepted_values.to is None
    assert accepted_values.field is None

    assert relationships.kind is GenericTestKind.RELATIONSHIPS
    assert relationships.to == "n2"
    assert relationships.field == "candidate_id"
    assert relationships.values == []

    candidate_id = node.fields[1]
    assert candidate_id.cast_to is None
    assert candidate_id.tests == []


def test_field_loads_cast_to_and_all_test_kinds_from_yaml(tmp_path: Path) -> None:
    """A field's `cast_to` override and each `FieldTest` kind load correctly from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_expected_fields(graph)


def test_field_loads_cast_to_and_all_test_kinds_from_json(tmp_path: Path) -> None:
    """A field's `cast_to` override and each `FieldTest` kind load correctly from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_expected_fields(graph)


def test_yaml_round_trip_is_stable_with_cast_to_and_tests(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for YAML, `cast_to`/`tests` included."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    loaded = load_graph_from_yaml(path)

    dump_path = tmp_path / "dumped.yaml"
    dump_graph_to_yaml(loaded, dump_path)
    reloaded = load_graph_from_yaml(dump_path)

    assert loaded == reloaded
    assert reloaded.nodes[0].fields[0].cast_to == "TIMESTAMP"
    assert len(reloaded.nodes[0].fields[0].tests) == 4

    # dump -> load -> dump idempotence
    redump_path = tmp_path / "redumped.yaml"
    dump_graph_to_yaml(reloaded, redump_path)
    assert dump_path.read_text() == redump_path.read_text()


def test_json_round_trip_is_stable_with_cast_to_and_tests(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for JSON, `cast_to`/`tests` included."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    loaded = load_graph_from_json(path)

    dump_path = tmp_path / "dumped.json"
    dump_graph_to_json(loaded, dump_path)
    reloaded = load_graph_from_json(dump_path)

    assert loaded == reloaded
    assert reloaded.nodes[0].fields[0].cast_to == "TIMESTAMP"
    assert len(reloaded.nodes[0].fields[0].tests) == 4

    # dump -> load -> dump idempotence
    redump_path = tmp_path / "redumped.json"
    dump_graph_to_json(reloaded, redump_path)
    assert dump_path.read_text() == redump_path.read_text()


def test_plain_field_with_no_cast_to_or_tests_is_unchanged() -> None:
    """A DANDER-4-shaped field (`name`/`type` only) still loads with backward-compat defaults."""
    field = NodeField(name="candidate_id", type="STRING")
    assert field.cast_to is None
    assert field.tests == []


def test_plain_field_round_trips_like_a_dander4_field(tmp_path: Path) -> None:
    """A field with no `cast_to`/`tests` round-trips exactly as a DANDER-4 field did."""
    graph = PipelineGraph(
        name="g",
        nodes=[
            Node(id="n1", type="source", name="a", fields=[NodeField(name="x", type="STRING")]),
            Node(id="n2", type="target", name="b"),
        ],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    reloaded_yaml = load_graph_from_yaml(yaml_path)
    assert graph == reloaded_yaml
    assert reloaded_yaml.nodes[0].fields[0].cast_to is None
    assert reloaded_yaml.nodes[0].fields[0].tests == []

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    reloaded_json = load_graph_from_json(json_path)
    assert graph == reloaded_json
    assert reloaded_json.nodes[0].fields[0].cast_to is None
    assert reloaded_json.nodes[0].fields[0].tests == []


# --- Boundary constraints ---------------------------------------------------------------------


def test_accepted_values_kind_rejects_missing_values() -> None:
    """`ACCEPTED_VALUES` kind with no `values` at all raises `ValidationError`."""
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.ACCEPTED_VALUES)


def test_accepted_values_kind_rejects_empty_values() -> None:
    """`ACCEPTED_VALUES` kind with an explicitly empty `values` list raises `ValidationError`."""
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.ACCEPTED_VALUES, values=[])


def test_accepted_values_kind_rejects_to_or_field_set() -> None:
    """`ACCEPTED_VALUES` kind with `to`/`field` also set raises `ValidationError`."""
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.ACCEPTED_VALUES, values=["a"], to="n2")
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.ACCEPTED_VALUES, values=["a"], field="f")


def test_relationships_kind_rejects_missing_field() -> None:
    """`RELATIONSHIPS` kind with no `field` at all raises `ValidationError`."""
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.RELATIONSHIPS, to="n2")


def test_relationships_kind_rejects_empty_field() -> None:
    """`RELATIONSHIPS` kind with an empty/whitespace-only `field` raises `ValidationError`."""
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.RELATIONSHIPS, to="n2", field="")
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.RELATIONSHIPS, to="n2", field="   ")


def test_relationships_kind_rejects_missing_to() -> None:
    """`RELATIONSHIPS` kind with no `to` node id raises `ValidationError`.

    The Design's implementation recommendation is followed: "referencing another node/field"
    names both the node (`to`) and the field (`field`), and a `field` reference with no `to`
    node is structurally dangling, so both are required.
    """
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.RELATIONSHIPS, field="candidate_id")


def test_relationships_kind_rejects_values_set() -> None:
    """`RELATIONSHIPS` kind with `values` also set raises `ValidationError`."""
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.RELATIONSHIPS, to="n2", field="candidate_id", values=["a"])


def test_not_null_kind_rejects_values_or_relationship_params() -> None:
    """`NOT_NULL` kind rejects a set `values`, `to`, or `field`."""
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.NOT_NULL, values=["a"])
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.NOT_NULL, to="n2")
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.NOT_NULL, field="f")


def test_unique_kind_rejects_values_or_relationship_params() -> None:
    """`UNIQUE` kind rejects a set `values`, `to`, or `field`."""
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.UNIQUE, values=["a"])
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.UNIQUE, to="n2")
    with pytest.raises(ValidationError):
        FieldTest(kind=GenericTestKind.UNIQUE, field="f")


def test_out_of_set_kind_is_rejected() -> None:
    """An out-of-set `kind` string fails validation at the Pydantic boundary."""
    with pytest.raises(ValidationError):
        FieldTest(kind="bogus_kind")


def test_not_null_and_unique_kinds_are_valid_with_no_payload() -> None:
    """`NOT_NULL`/`UNIQUE` kinds are valid with no additional payload set."""
    not_null = FieldTest(kind=GenericTestKind.NOT_NULL)
    assert not_null.values == []
    assert not_null.to is None
    assert not_null.field is None

    unique = FieldTest(kind=GenericTestKind.UNIQUE)
    assert unique.values == []
