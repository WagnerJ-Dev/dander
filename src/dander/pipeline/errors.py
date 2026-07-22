"""Typed error hierarchy for pipeline-graph structural validation.

A `PipelineGraph` (see `dander.pipeline.graph`) is only safe to hand to the orchestration layer
once it is known to be structurally sound: unique node ids, no dangling edge endpoints, no
self-loops, and no cycles. This module defines one typed error per failure mode, each naming the
offending element(s) so failures are loud and actionable (per `steering/02-engineering.md`).

Error messages contain graph **structure only** — node/edge ids — and never a node's free-form
``config`` values or edge ``metadata``, which may carry sensitive data (per
`steering/01-security.md`).
"""

from __future__ import annotations


class GraphValidationError(Exception):
    """Root of the pipeline-graph validation error hierarchy.

    Raised (via a subclass) whenever a `PipelineGraph` fails a structural check. Catch this type
    to handle any structural failure generically, or a specific subclass to handle one failure
    mode.
    """


class DuplicateNodeIdError(GraphValidationError):
    """Raised when two or more nodes in a graph share the same `id`.

    Attributes:
        node_id: The duplicated node id.
    """

    def __init__(self, node_id: str) -> None:
        """Initialize the error for a duplicated node id.

        Args:
            node_id: The node id that appears more than once in the graph.
        """
        self.node_id = node_id
        super().__init__(f"Duplicate node id: {node_id!r} appears more than once in the graph.")


class DanglingEdgeError(GraphValidationError):
    """Raised when an edge references a node id that does not exist in the graph.

    Attributes:
        source: The edge's `from` node id.
        target: The edge's `to` node id.
        missing_id: Whichever of `source`/`target` is not a known node id.
    """

    def __init__(self, *, source: str, target: str, missing_id: str) -> None:
        """Initialize the error for a dangling edge.

        Args:
            source: The edge's `from` node id.
            target: The edge's `to` node id.
            missing_id: The endpoint (equal to `source` or `target`) that has no matching node.
        """
        self.source = source
        self.target = target
        self.missing_id = missing_id
        super().__init__(
            f"Dangling edge {source!r} -> {target!r}: node id {missing_id!r} does not exist."
        )


class SelfLoopError(GraphValidationError):
    """Raised when an edge's `from` and `to` refer to the same node (a self-loop).

    Attributes:
        node_id: The node id that has an edge to itself.
    """

    def __init__(self, node_id: str) -> None:
        """Initialize the error for a self-loop.

        Args:
            node_id: The node id targeted by an edge from itself.
        """
        self.node_id = node_id
        super().__init__(f"Self-loop detected: node {node_id!r} has an edge to itself.")


class GraphCycleError(GraphValidationError):
    """Raised when the graph contains a cycle (it is not a DAG).

    Attributes:
        cycle: The cycle path as a list of node ids in visitation order, with the start node
            repeated at the end to close the loop (e.g. `["a", "b", "c", "a"]`).
    """

    def __init__(self, cycle: list[str]) -> None:
        """Initialize the error with the detected cycle path.

        Args:
            cycle: The cycle path, start node repeated at the end (e.g. `["a", "b", "c", "a"]`).
        """
        self.cycle = cycle
        super().__init__(f"Cycle detected in graph: {' -> '.join(cycle)}")
