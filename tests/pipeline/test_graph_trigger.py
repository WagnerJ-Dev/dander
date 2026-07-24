"""Unit tests for ``TriggerKind``/``Trigger`` and `PipelineGraph.trigger`/`Node.trigger`
(DANDER-14).

Covers the declarative trigger/schedule model attachable at the pipeline and node level:
intra-model boundary constraints (closed trigger-kind set, per-kind required/forbidden payload),
stable round-trip through both YAML and JSON, and backward compatibility of a trigger-less
pipeline/node (unchanged dump, no `trigger` key emitted). No scheduler, cron evaluation, or
execution is in scope here — this is model + serialization only, matching the rest of
`dander.pipeline.graph`; a future Orchestration/State layer consumes this model per
`steering/00-project-overview.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from dander.pipeline.graph import (
    Node,
    PipelineGraph,
    Trigger,
    TriggerKind,
    dump_graph_to_json,
    dump_graph_to_yaml,
    load_graph_from_json,
    load_graph_from_yaml,
)

if TYPE_CHECKING:
    from pathlib import Path

_YAML_DOC = """
name: candidate_ingest
trigger:
  kind: schedule
  cron: "0 6 * * *"
nodes:
  - id: n1
    type: source
    name: extract_candidates
  - id: n2
    type: task
    name: notify_slack
    trigger:
      kind: manual
edges:
  - from: n1
    to: n2
"""

_JSON_DOC = """
{
  "name": "candidate_ingest",
  "trigger": {"kind": "schedule", "cron": "0 6 * * *"},
  "nodes": [
    {"id": "n1", "type": "source", "name": "extract_candidates"},
    {
      "id": "n2",
      "type": "task",
      "name": "notify_slack",
      "trigger": {"kind": "manual"}
    }
  ],
  "edges": [{"from": "n1", "to": "n2"}]
}
"""

_DEPENDENCY_YAML_DOC = """
name: candidate_ingest
trigger:
  kind: dependency
  depends_on:
    - upstream_pipeline_a
    - upstream_pipeline_b
nodes:
  - id: n1
    type: source
    name: extract_candidates
edges: []
"""

_DEPENDENCY_JSON_DOC = """
{
  "name": "candidate_ingest",
  "trigger": {"kind": "dependency", "depends_on": ["upstream_pipeline_a", "upstream_pipeline_b"]},
  "nodes": [{"id": "n1", "type": "source", "name": "extract_candidates"}],
  "edges": []
}
"""

_MANUAL_WITH_EVENT_YAML_DOC = """
name: candidate_ingest
nodes:
  - id: n1
    type: task
    name: reindex
    trigger:
      kind: manual
      event: candidate.updated
edges: []
"""

_MANUAL_WITH_EVENT_JSON_DOC = """
{
  "name": "candidate_ingest",
  "nodes": [
    {
      "id": "n1",
      "type": "task",
      "name": "reindex",
      "trigger": {"kind": "manual", "event": "candidate.updated"}
    }
  ],
  "edges": []
}
"""


def _assert_schedule_and_manual(graph: PipelineGraph) -> None:
    assert graph.trigger is not None
    assert graph.trigger.kind is TriggerKind.SCHEDULE
    assert graph.trigger.cron == "0 6 * * *"
    assert graph.trigger.depends_on == []
    assert graph.trigger.event is None

    node2 = graph.nodes[1]
    assert node2.trigger is not None
    assert node2.trigger.kind is TriggerKind.MANUAL
    assert node2.trigger.event is None
    assert node2.trigger.cron is None
    assert node2.trigger.depends_on == []

    node1 = graph.nodes[0]
    assert node1.trigger is None


def test_pipeline_loads_schedule_trigger_from_yaml(tmp_path: Path) -> None:
    """A pipeline loads a graph-level SCHEDULE trigger (opaque cron string) from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_schedule_and_manual(graph)


def test_pipeline_loads_schedule_trigger_from_json(tmp_path: Path) -> None:
    """A pipeline loads a graph-level SCHEDULE trigger (opaque cron string) from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_schedule_and_manual(graph)


def _assert_dependency_trigger(graph: PipelineGraph) -> None:
    assert graph.trigger is not None
    assert graph.trigger.kind is TriggerKind.DEPENDENCY
    assert graph.trigger.depends_on == ["upstream_pipeline_a", "upstream_pipeline_b"]
    assert graph.trigger.cron is None
    assert graph.trigger.event is None


def test_pipeline_loads_dependency_trigger_from_yaml(tmp_path: Path) -> None:
    """A pipeline loads a graph-level DEPENDENCY trigger (non-empty depends_on) from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_DEPENDENCY_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_dependency_trigger(graph)


def test_pipeline_loads_dependency_trigger_from_json(tmp_path: Path) -> None:
    """A pipeline loads a graph-level DEPENDENCY trigger (non-empty depends_on) from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_DEPENDENCY_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_dependency_trigger(graph)


def _assert_manual_with_event(graph: PipelineGraph) -> None:
    node = graph.nodes[0]
    assert node.trigger is not None
    assert node.trigger.kind is TriggerKind.MANUAL
    assert node.trigger.event == "candidate.updated"
    assert node.trigger.cron is None
    assert node.trigger.depends_on == []


def test_node_loads_manual_trigger_with_event_from_yaml(tmp_path: Path) -> None:
    """A node loads a MANUAL trigger with an event name from YAML."""
    path = tmp_path / "graph.yaml"
    path.write_text(_MANUAL_WITH_EVENT_YAML_DOC)
    graph = load_graph_from_yaml(path)
    _assert_manual_with_event(graph)


def test_node_loads_manual_trigger_with_event_from_json(tmp_path: Path) -> None:
    """A node loads a MANUAL trigger with an event name from JSON."""
    path = tmp_path / "graph.json"
    path.write_text(_MANUAL_WITH_EVENT_JSON_DOC)
    graph = load_graph_from_json(path)
    _assert_manual_with_event(graph)


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "schedule"},
        {"kind": "schedule", "cron": ""},
        {"kind": "schedule", "cron": "   "},
        {"kind": "schedule", "cron": "0 6 * * *", "depends_on": ["a"]},
        {"kind": "schedule", "cron": "0 6 * * *", "event": "x"},
        {"kind": "dependency"},
        {"kind": "dependency", "depends_on": []},
        {"kind": "dependency", "depends_on": ["a"], "cron": "0 6 * * *"},
        {"kind": "dependency", "depends_on": ["a"], "event": "x"},
        {"kind": "manual", "cron": "0 6 * * *"},
        {"kind": "manual", "depends_on": ["a"]},
        {"kind": "bogus"},
        {},
    ],
)
def test_trigger_rejects_malformed_payload(payload: dict[str, object]) -> None:
    """A malformed trigger (bad kind, missing kind, or wrong per-kind payload) raises
    `ValidationError` at the boundary."""
    with pytest.raises(ValidationError):
        Trigger.model_validate(payload)


def test_trigger_constructs_directly_for_each_kind() -> None:
    """`Trigger` constructs directly with attribute names for each valid kind."""
    schedule = Trigger(kind=TriggerKind.SCHEDULE, cron="*/5 * * * *")
    assert schedule.kind is TriggerKind.SCHEDULE
    assert schedule.cron == "*/5 * * * *"

    dependency = Trigger(kind=TriggerKind.DEPENDENCY, depends_on=["upstream"])
    assert dependency.kind is TriggerKind.DEPENDENCY
    assert dependency.depends_on == ["upstream"]

    manual = Trigger(kind=TriggerKind.MANUAL)
    assert manual.kind is TriggerKind.MANUAL
    assert manual.event is None

    manual_event = Trigger(kind=TriggerKind.MANUAL, event="candidate.updated")
    assert manual_event.event == "candidate.updated"


def test_yaml_round_trip_is_stable_with_trigger(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for YAML, including graph- and node-level
    triggers and metadata."""
    graph = PipelineGraph(
        name="g",
        trigger=Trigger(
            kind=TriggerKind.SCHEDULE, cron="0 6 * * *", metadata={"owner": "data-eng"}
        ),
        nodes=[
            Node(
                id="n1",
                type="task",
                name="a",
                trigger=Trigger(kind=TriggerKind.DEPENDENCY, depends_on=["upstream"]),
            ),
            Node(id="n2", type="task", name="b"),
        ],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    loaded = load_graph_from_yaml(yaml_path)
    assert loaded == graph

    dump_path_2 = tmp_path / "dumped2.yaml"
    dump_graph_to_yaml(loaded, dump_path_2)
    reloaded_again = load_graph_from_yaml(dump_path_2)
    assert loaded == reloaded_again


def test_json_round_trip_is_stable_with_trigger(tmp_path: Path) -> None:
    """Load -> dump -> load yields an equivalent graph for JSON, including graph- and node-level
    triggers and metadata."""
    graph = PipelineGraph(
        name="g",
        trigger=Trigger(
            kind=TriggerKind.SCHEDULE, cron="0 6 * * *", metadata={"owner": "data-eng"}
        ),
        nodes=[
            Node(
                id="n1",
                type="task",
                name="a",
                trigger=Trigger(kind=TriggerKind.DEPENDENCY, depends_on=["upstream"]),
            ),
            Node(id="n2", type="task", name="b"),
        ],
    )

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    loaded = load_graph_from_json(json_path)
    assert loaded == graph

    dump_path_2 = tmp_path / "dumped2.json"
    dump_graph_to_json(loaded, dump_path_2)
    reloaded_again = load_graph_from_json(dump_path_2)
    assert loaded == reloaded_again


def test_manual_trigger_without_event_round_trips_stably_both_formats(tmp_path: Path) -> None:
    """A MANUAL trigger with `event` unset round-trips stably in both formats, guarding the
    value-vs-presence validator reasoning across a dump/load cycle."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="task", name="a", trigger=Trigger(kind=TriggerKind.MANUAL))],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_loaded = load_graph_from_yaml(yaml_path)
    assert yaml_loaded == graph
    dump_graph_to_yaml(yaml_loaded, tmp_path / "graph2.yaml")
    assert load_graph_from_yaml(tmp_path / "graph2.yaml") == yaml_loaded

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_loaded = load_graph_from_json(json_path)
    assert json_loaded == graph
    dump_graph_to_json(json_loaded, tmp_path / "graph2.json")
    assert load_graph_from_json(tmp_path / "graph2.json") == json_loaded


def test_trigger_less_pipeline_round_trips_unchanged_and_omits_trigger_key(
    tmp_path: Path,
) -> None:
    """A trigger-less pipeline round-trips equal and its dumped YAML/JSON text carries no
    `trigger` key at either the graph or node level."""
    graph = PipelineGraph(
        name="g",
        nodes=[Node(id="n1", type="task", name="a"), Node(id="n2", type="task", name="b")],
    )
    assert graph.trigger is None
    assert all(node.trigger is None for node in graph.nodes)

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_text = yaml_path.read_text()
    assert "trigger" not in yaml_text
    reloaded_yaml = load_graph_from_yaml(yaml_path)
    assert reloaded_yaml == graph
    assert reloaded_yaml.trigger is None
    assert all(node.trigger is None for node in reloaded_yaml.nodes)

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_text = json_path.read_text()
    assert "trigger" not in json_text
    reloaded_json = load_graph_from_json(json_path)
    assert reloaded_json == graph
    assert reloaded_json.trigger is None
    assert all(node.trigger is None for node in reloaded_json.nodes)


def test_graph_and_node_with_trigger_dump_nested_trigger_block(tmp_path: Path) -> None:
    """A graph/node with a trigger dumps a nested `trigger` block with `kind` + payload, both
    formats."""
    graph = PipelineGraph(
        name="g",
        trigger=Trigger(kind=TriggerKind.SCHEDULE, cron="0 6 * * *"),
        nodes=[
            Node(
                id="n1",
                type="task",
                name="a",
                trigger=Trigger(kind=TriggerKind.DEPENDENCY, depends_on=["upstream"]),
            )
        ],
    )

    yaml_path = tmp_path / "graph.yaml"
    dump_graph_to_yaml(graph, yaml_path)
    yaml_text = yaml_path.read_text()
    assert "trigger:" in yaml_text
    assert "kind: schedule" in yaml_text
    assert "cron: 0 6 * * *" in yaml_text
    assert "kind: dependency" in yaml_text
    assert "- upstream" in yaml_text

    json_path = tmp_path / "graph.json"
    dump_graph_to_json(graph, json_path)
    json_text = json_path.read_text()
    assert '"trigger"' in json_text
    assert '"kind": "schedule"' in json_text
    assert '"cron": "0 6 * * *"' in json_text
    assert '"kind": "dependency"' in json_text
    assert '"upstream"' in json_text
