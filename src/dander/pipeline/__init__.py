"""Pipeline graph module: declarative Node/Edge/PipelineGraph model + YAML/JSON serialization.

Validation (uniqueness, dangling edges, self-loops, DAG/cycle detection), field-wiring validation
(duplicate field names, unresolved mapping/transformation/join field references), and derived
graph algorithms (adjacency, topological order) build on top of these models in
`dander.pipeline.graph_ops`.
"""

from __future__ import annotations

from dander.pipeline.compiler import (
    CompiledTarget,
    PipelineCompileError,
    PreparedTargetWriter,
    compile_target,
    prepare_target_writer,
)
from dander.pipeline.errors import (
    DanglingEdgeError,
    DuplicateFieldNameError,
    DuplicateNodeIdError,
    FieldReferenceKind,
    GraphCycleError,
    GraphValidationError,
    JoinKeyFieldError,
    SelfLoopError,
    UnknownFieldReferenceError,
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
from dander.pipeline.graph_ops import (
    AdjacencyIndex,
    topological_order,
    validate,
    validate_field_wiring,
)
from dander.pipeline.node_config import (
    DestinationSpec,
    ExecutableJoinKey,
    ExecutableJoinType,
    NodeConfig,
    NodeType,
    PartitioningSpec,
    PartitioningType,
    SourceNodeConfig,
    TargetNodeConfig,
    TransformJoinConfig,
    TransformNodeConfig,
    WriterConfig,
)
from dander.pipeline.request_spec import HttpMethod, RequestSpec

__all__ = [
    "AdjacencyIndex",
    "CompiledTarget",
    "DanglingEdgeError",
    "DestinationSpec",
    "DuplicateFieldNameError",
    "DuplicateNodeIdError",
    "Edge",
    "ExecutableJoinKey",
    "ExecutableJoinType",
    "FieldReferenceKind",
    "GraphCycleError",
    "GraphValidationError",
    "HttpMethod",
    "JoinKeyFieldError",
    "Node",
    "NodeConfig",
    "NodeType",
    "PartitioningSpec",
    "PartitioningType",
    "PipelineGraph",
    "PipelineCompileError",
    "PreparedTargetWriter",
    "RequestSpec",
    "SelfLoopError",
    "SourceNodeConfig",
    "TargetNodeConfig",
    "TransformNodeConfig",
    "TransformJoinConfig",
    "UnknownFieldReferenceError",
    "WriterConfig",
    "dump_graph_to_json",
    "dump_graph_to_yaml",
    "compile_target",
    "load_graph_from_json",
    "load_graph_from_yaml",
    "topological_order",
    "prepare_target_writer",
    "validate",
    "validate_field_wiring",
]
