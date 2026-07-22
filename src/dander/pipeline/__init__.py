"""Pipeline graph module: declarative Node/Edge/PipelineGraph model + YAML/JSON serialization.

Validation (uniqueness, dangling edges, self-loops, DAG/cycle detection) and derived graph
algorithms (adjacency, topological order) build on top of these models in
`dander.pipeline.graph_ops`.
"""

from __future__ import annotations

from dander.pipeline.errors import (
    DanglingEdgeError,
    DuplicateNodeIdError,
    GraphCycleError,
    GraphValidationError,
    SelfLoopError,
)
from dander.pipeline.graph import (
    Edge,
    Node,
    PipelineGraph,
    dump_graph_to_json,
    dump_graph_to_yaml,
    load_graph_from_json,
    load_graph_from_yaml,
)
from dander.pipeline.graph_ops import AdjacencyIndex, topological_order, validate

__all__ = [
    "AdjacencyIndex",
    "DanglingEdgeError",
    "DuplicateNodeIdError",
    "Edge",
    "GraphCycleError",
    "GraphValidationError",
    "Node",
    "PipelineGraph",
    "SelfLoopError",
    "dump_graph_to_json",
    "dump_graph_to_yaml",
    "load_graph_from_json",
    "load_graph_from_yaml",
    "topological_order",
    "validate",
]
