"""Unit tests for ``dander.pipeline.graph_ops`` (validation, adjacency, topological order)."""

from __future__ import annotations

import pytest

from dander.pipeline.errors import (
    DanglingEdgeError,
    DuplicateNodeIdError,
    GraphCycleError,
    SelfLoopError,
)
from dander.pipeline.graph import Edge, Node, PipelineGraph
from dander.pipeline.graph_ops import AdjacencyIndex, topological_order, validate


def _node(node_id: str) -> Node:
    return Node(id=node_id, type="task", name=node_id)


def _edge(source: str, target: str) -> Edge:
    return Edge(source=source, target=target)


def test_valid_graph_validates_without_raising() -> None:
    """A valid multi-node/multi-edge DAG passes `validate` with no error raised."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("a"), _node("b"), _node("c")],
        edges=[_edge("a", "b"), _edge("b", "c")],
    )
    validate(graph)  # should not raise


def test_duplicate_node_id_raises_with_offending_id() -> None:
    """Two nodes sharing an id raise `DuplicateNodeIdError` naming that id."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("a"), _node("a")],
        edges=[],
    )
    with pytest.raises(DuplicateNodeIdError) as exc_info:
        validate(graph)
    assert exc_info.value.node_id == "a"
    assert "a" in str(exc_info.value)


def test_dangling_edge_raises_with_edge_and_missing_id() -> None:
    """An edge referencing an unknown node id raises `DanglingEdgeError` naming it."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("a")],
        edges=[_edge("a", "ghost")],
    )
    with pytest.raises(DanglingEdgeError) as exc_info:
        validate(graph)
    err = exc_info.value
    assert err.source == "a"
    assert err.target == "ghost"
    assert err.missing_id == "ghost"
    assert "ghost" in str(err)


def test_self_loop_raises_with_offending_node() -> None:
    """An edge from a node to itself raises `SelfLoopError` naming that node."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("a")],
        edges=[_edge("a", "a")],
    )
    with pytest.raises(SelfLoopError) as exc_info:
        validate(graph)
    assert exc_info.value.node_id == "a"
    assert "a" in str(exc_info.value)


def test_cycle_raises_with_cycle_path() -> None:
    """A cyclic graph raises `GraphCycleError` reporting the actual cycle path."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("a"), _node("b"), _node("c")],
        edges=[_edge("a", "b"), _edge("b", "c"), _edge("c", "a")],
    )
    with pytest.raises(GraphCycleError) as exc_info:
        validate(graph)
    cycle = exc_info.value.cycle
    # The cycle path starts and ends on the same node, and every consecutive pair is a real edge.
    assert cycle[0] == cycle[-1]
    assert set(cycle) == {"a", "b", "c"}
    edges = {(e.source, e.target) for e in graph.edges}
    for source, target in zip(cycle, cycle[1:], strict=False):
        assert (source, target) in edges


def test_adjacency_index_successors_and_predecessors() -> None:
    """`AdjacencyIndex` returns exact expected neighbours, including for a node with none."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("a"), _node("b"), _node("c"), _node("isolated")],
        edges=[_edge("a", "b"), _edge("a", "c"), _edge("b", "c")],
    )
    index = AdjacencyIndex.from_graph(graph)

    assert index.successors("a") == ["b", "c"]
    assert index.successors("b") == ["c"]
    assert index.successors("c") == []
    assert index.successors("isolated") == []

    assert index.predecessors("a") == []
    assert index.predecessors("b") == ["a"]
    assert index.predecessors("c") == ["a", "b"]
    assert index.predecessors("isolated") == []


def test_adjacency_index_lookups_are_independent_copies() -> None:
    """Mutating a returned neighbour list must not corrupt the index's internal state."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("a"), _node("b")],
        edges=[_edge("a", "b")],
    )
    index = AdjacencyIndex.from_graph(graph)
    index.successors("a").append("z")
    assert index.successors("a") == ["b"]


def test_topological_order_respects_all_edges() -> None:
    """`topological_order` returns an ordering where every edge's source precedes its target."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("a"), _node("b"), _node("c"), _node("d")],
        edges=[_edge("a", "b"), _edge("a", "c"), _edge("b", "d"), _edge("c", "d")],
    )
    order = topological_order(graph)

    assert set(order) == {"a", "b", "c", "d"}
    position = {node_id: i for i, node_id in enumerate(order)}
    for edge in graph.edges:
        assert position[edge.source] < position[edge.target]


def test_topological_order_raises_graph_cycle_error_on_cyclic_graph() -> None:
    """Calling `topological_order` on a cyclic graph raises `GraphCycleError`."""
    graph = PipelineGraph(
        name="g",
        nodes=[_node("a"), _node("b")],
        edges=[_edge("a", "b"), _edge("b", "a")],
    )
    with pytest.raises(GraphCycleError):
        topological_order(graph)
