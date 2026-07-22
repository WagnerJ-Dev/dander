"""Derived structure and algorithms over a `PipelineGraph`.

This module is the correctness layer that sits on top of DANDER-2's pure `PipelineGraph` model:
structural validation (`validate`), a derived adjacency index (`AdjacencyIndex`), and execution
ordering (`topological_order`). Everything here is a pure, side-effect-free function of a
`PipelineGraph` — nothing is persisted onto the model, and adjacency is always computed from the
stored `edges` list, never stored twice (per the decided format in
`steering/00-project-overview.md`).

Kept out of `dander.pipeline.graph` so the model stays a pure value object (SRP) and so algorithms
depend on the model, never the reverse (DIP) — no import cycle between shape and behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dander.pipeline.errors import (
    DanglingEdgeError,
    DuplicateNodeIdError,
    GraphCycleError,
    SelfLoopError,
)

if TYPE_CHECKING:
    from dander.pipeline.graph import PipelineGraph

_WHITE = 0  # not yet visited
_GREY = 1  # on the current DFS recursion stack (in progress)
_BLACK = 2  # fully processed


@dataclass(frozen=True)
class AdjacencyIndex:
    """Derived predecessor/successor lookup for a `PipelineGraph`, computed once from `edges`.

    Built after (or by an internal caller that guarantees) the duplicate-id and dangling-edge
    checks have passed — `from_graph` does not itself re-validate. Neighbour ids are kept in
    edge-insertion order so lookups are deterministic.

    Attributes:
        _successors: Node id -> ids it has outgoing edges to, in edge-insertion order.
        _predecessors: Node id -> ids it has incoming edges from, in edge-insertion order.
    """

    _successors: dict[str, list[str]]
    _predecessors: dict[str, list[str]]

    @classmethod
    def from_graph(cls, graph: PipelineGraph) -> AdjacencyIndex:
        """Build an `AdjacencyIndex` from a graph's `edges` list.

        Assumes node ids are already known-unique and every edge endpoint is a valid node id
        (i.e. called after, or as part of, structural validation) — for internal use where that
        is guaranteed, this does not re-check either invariant itself.

        Args:
            graph: The pipeline graph to index.

        Returns:
            An `AdjacencyIndex` with every node id present (mapping to an empty list if it has
            no incident edges).
        """
        successors: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
        predecessors: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
        for edge in graph.edges:
            successors.setdefault(edge.source, []).append(edge.target)
            predecessors.setdefault(edge.target, []).append(edge.source)
        return cls(_successors=successors, _predecessors=predecessors)

    def successors(self, node_id: str) -> list[str]:
        """Return the ids this node has outgoing edges to.

        Args:
            node_id: The node id to look up.

        Returns:
            A new list of successor node ids in edge-insertion order (empty if none, or if
            `node_id` is unknown to this index).
        """
        return list(self._successors.get(node_id, []))

    def predecessors(self, node_id: str) -> list[str]:
        """Return the ids this node has incoming edges from.

        Args:
            node_id: The node id to look up.

        Returns:
            A new list of predecessor node ids in edge-insertion order (empty if none, or if
            `node_id` is unknown to this index).
        """
        return list(self._predecessors.get(node_id, []))


def _check_duplicate_node_ids(graph: PipelineGraph) -> None:
    """Raise `DuplicateNodeIdError` if any two nodes share an `id`."""
    seen: set[str] = set()
    for node in graph.nodes:
        if node.id in seen:
            raise DuplicateNodeIdError(node.id)
        seen.add(node.id)


def _check_dangling_edges(graph: PipelineGraph) -> None:
    """Raise `DanglingEdgeError` if any edge endpoint is not a known node id."""
    node_ids = {node.id for node in graph.nodes}
    for edge in graph.edges:
        if edge.source not in node_ids:
            raise DanglingEdgeError(source=edge.source, target=edge.target, missing_id=edge.source)
        if edge.target not in node_ids:
            raise DanglingEdgeError(source=edge.source, target=edge.target, missing_id=edge.target)


def _check_self_loops(graph: PipelineGraph) -> None:
    """Raise `SelfLoopError` if any edge's `source` equals its `target`."""
    for edge in graph.edges:
        if edge.source == edge.target:
            raise SelfLoopError(edge.source)


def _dfs_topological_order(node_ids: list[str], adjacency: AdjacencyIndex) -> list[str]:
    """Compute a topological order via DFS with three-colour marking.

    Visits nodes and their successors in insertion order (the order of `node_ids` and of each
    node's successor list) so the result is deterministic. If DFS reaches a grey (in-progress)
    node, the graph has a cycle; the current recursion stack is sliced from that node to the
    current one to report the cycle path.

    Args:
        node_ids: All node ids in the graph, in insertion order.
        adjacency: The graph's derived adjacency index.

    Returns:
        Node ids in a valid execution order: for every edge, its source appears before its
        target.

    Raises:
        GraphCycleError: If the graph is not a DAG. The error's `cycle` attribute holds the
            cycle path, start node repeated at the end.
    """
    color: dict[str, int] = dict.fromkeys(node_ids, _WHITE)
    order: list[str] = []
    stack_path: list[str] = []

    def visit(node_id: str) -> None:
        color[node_id] = _GREY
        stack_path.append(node_id)
        for neighbor in adjacency.successors(node_id):
            if color[neighbor] == _WHITE:
                visit(neighbor)
            elif color[neighbor] == _GREY:
                cycle_start = stack_path.index(neighbor)
                raise GraphCycleError([*stack_path[cycle_start:], neighbor])
            # _BLACK neighbours are already fully processed; nothing to do.
        stack_path.pop()
        color[node_id] = _BLACK
        order.append(node_id)

    for node_id in node_ids:
        if color[node_id] == _WHITE:
            visit(node_id)

    order.reverse()
    return order


def _check_acyclic(graph: PipelineGraph) -> None:
    """Raise `GraphCycleError` if the graph is not a DAG.

    Assumes node ids are unique and every edge endpoint is a known node id (i.e. called after
    the duplicate-id and dangling-edge checks).
    """
    adjacency = AdjacencyIndex.from_graph(graph)
    node_ids = [node.id for node in graph.nodes]
    _dfs_topological_order(node_ids, adjacency)


def validate(graph: PipelineGraph) -> None:
    """Validate a `PipelineGraph`'s structural correctness.

    Runs four checks in a fixed order, each assuming the earlier ones held: (1) node ids are
    unique; (2) every edge endpoint references an existing node id; (3) no edge is a self-loop;
    (4) the graph is a DAG (no cycle). The order matters because later checks (adjacency, cycle
    detection) are only meaningful once ids are unique and every edge endpoint resolves.

    Args:
        graph: The pipeline graph to validate.

    Raises:
        DuplicateNodeIdError: Two or more nodes share the same `id`.
        DanglingEdgeError: An edge references a node id that does not exist.
        SelfLoopError: An edge's `from` and `to` are the same node.
        GraphCycleError: The graph contains a cycle.
    """
    _check_duplicate_node_ids(graph)
    _check_dangling_edges(graph)
    _check_self_loops(graph)
    _check_acyclic(graph)


def topological_order(graph: PipelineGraph) -> list[str]:
    """Return the graph's node ids in a valid execution order.

    Validates the graph first (see `validate`), so an invalid graph raises the corresponding
    typed error — including `GraphCycleError` for a cyclic graph — rather than returning a
    meaningless order.

    Args:
        graph: The pipeline graph to order.

    Returns:
        Node ids ordered so that for every edge, its source appears before its target.

    Raises:
        DuplicateNodeIdError: Two or more nodes share the same `id`.
        DanglingEdgeError: An edge references a node id that does not exist.
        SelfLoopError: An edge's `from` and `to` are the same node.
        GraphCycleError: The graph contains a cycle.
    """
    validate(graph)
    adjacency = AdjacencyIndex.from_graph(graph)
    node_ids = [node.id for node in graph.nodes]
    return _dfs_topological_order(node_ids, adjacency)
