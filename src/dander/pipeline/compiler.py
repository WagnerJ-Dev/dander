"""Compile the executable subset of a visual pipeline graph to BigQuery SQL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import sqlglot
from sqlglot import exp

from dander.pipeline.graph import TransformationKind
from dander.pipeline.graph_ops import validate_field_wiring
from dander.pipeline.node_config import TargetNodeConfig
from dander.writer import (
    BigQueryIncrementalWriter,
    BigQueryReplaceWriter,
    BigQueryScd1Writer,
    BigQueryScd2Writer,
    BigQuerySnapshotWriter,
    WriteMode,
    WritePattern,
    WriteTarget,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from dander.pipeline.graph import (
        Edge,
        FieldMapping,
        Node,
        NodeField,
        PipelineGraph,
        Transformation,
    )
    from dander.writer.bigquery import _BigQueryClient

_RELATION = re.compile(
    r"^[A-Za-z][A-Za-z0-9-]{4,61}[A-Za-z0-9]\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$"
)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TYPE = re.compile(
    r"^(?:BOOL|BOOLEAN|BYTES|DATE|DATETIME|FLOAT64|GEOGRAPHY|INT64|INTEGER|JSON|"
    r"NUMERIC|BIGNUMERIC|STRING|TIME|TIMESTAMP)$",
    re.IGNORECASE,
)
_ALLOWED_FUNCTIONS = frozenset(
    {
        "ABS",
        "CAST",
        "COALESCE",
        "CONCAT",
        "CURRENT_DATE",
        "CURRENT_DATETIME",
        "CURRENT_TIMESTAMP",
        "DATE",
        "DATETIME",
        "IF",
        "IFNULL",
        "LENGTH",
        "LOWER",
        "NULLIF",
        "REGEXP_EXTRACT",
        "REGEXP_REPLACE",
        "REPLACE",
        "ROUND",
        "SAFE_CAST",
        "SUBSTRING",
        "TIMESTAMP",
        "TRIM",
        "UPPER",
    }
)


class PipelineCompileError(ValueError):
    """Raised when a valid declarative graph has no safe executable interpretation."""


@dataclass(frozen=True)
class CompiledTarget:
    """A target SELECT plus its resolved write contract."""

    node_id: str
    query: str
    write_mode: WriteMode
    target: WriteTarget


@dataclass(frozen=True)
class PreparedTargetWriter:
    """A concrete writer bound to a graph target without performing a write."""

    writer: WritePattern
    target: WriteTarget

    def write(self, records: Iterable[Mapping[str, Any]]) -> int:
        """Send records through the selected idempotent write pattern."""
        return self.writer.write(records, self.target)


def compile_target(
    graph: PipelineGraph,
    target_node_id: str,
    *,
    source_relations: Mapping[str, str],
    default_project: str | None = None,
) -> CompiledTarget:
    """Compile one linear source-to-target graph path into a BigQuery SELECT.

    This first executable graph slice deliberately rejects joins and fan-in. The current graph
    schema puts a join's right input on the same node that also represents the edge output, so
    silently inventing execution semantics would be unsafe. Linear mappings, casts, expressions,
    constants, and allow-listed custom transforms are fully executable.
    """
    validate_field_wiring(graph)
    nodes = {node.id: node for node in graph.nodes}
    try:
        target = nodes[target_node_id]
    except KeyError as error:
        raise PipelineCompileError(f"Unknown target node {target_node_id!r}") from error
    config = target.config
    if target.type != "target" or not isinstance(config, TargetNodeConfig) or config.writer is None:
        raise PipelineCompileError(
            f"Node {target_node_id!r} must be a target with writer configuration"
        )

    incoming: dict[str, list[Edge]] = {node_id: [] for node_id in nodes}
    for edge in graph.edges:
        incoming[edge.target].append(edge)

    path: list[tuple[Node, Edge]] = []
    current = target
    while current.type != "source":
        if current.type not in {"transform", "target"}:
            raise PipelineCompileError(
                f"Node {current.id!r} has unsupported executable type {current.type!r}"
            )
        edges = incoming[current.id]
        if len(edges) != 1:
            raise PipelineCompileError(
                f"Node {current.id!r} requires exactly one incoming edge for execution"
            )
        edge = edges[0]
        if edge.join is not None:
            raise PipelineCompileError(
                "Executable joins require a distinct output node; the current edge join model "
                "does not distinguish its right input from its output"
            )
        path.append((current, edge))
        current = nodes[edge.source]
    if incoming[current.id]:
        raise PipelineCompileError(f"Source node {current.id!r} cannot have an incoming edge")
    path.reverse()

    relation = source_relations.get(current.id)
    if relation is None:
        raise PipelineCompileError(f"Missing source relation for node {current.id!r}")
    if not _RELATION.fullmatch(relation):
        raise PipelineCompileError(
            f"Source relation for node {current.id!r} must be project.dataset.table"
        )

    ctes: list[str] = []
    source_alias = "_node_0"
    source_columns = ", ".join(_compile_source_field(field) for field in current.fields)
    if not source_columns:
        raise PipelineCompileError(f"Source node {current.id!r} must declare fields")
    ctes.append(f"{_quote(source_alias)} AS (\n  SELECT {source_columns} FROM `{relation}`\n)")

    previous_alias = source_alias
    for index, (node, edge) in enumerate(path, start=1):
        if not edge.mappings:
            raise PipelineCompileError(f"Edge {edge.source!r}->{edge.target!r} has no mappings")
        mappings = {mapping.target: mapping for mapping in edge.mappings}
        if len(mappings) != len(edge.mappings):
            raise PipelineCompileError(
                f"Edge {edge.source!r}->{edge.target!r} maps a target field more than once"
            )
        missing = [field.name for field in node.fields if field.name not in mappings]
        if missing:
            raise PipelineCompileError(
                f"Edge {edge.source!r}->{edge.target!r} does not map target field {missing[0]!r}"
            )
        projected = [
            _compile_mapping(mappings[field.name], field.cast_to, alias="source")
            for field in node.fields
        ]
        current_alias = f"_node_{index}"
        select_list = ",\n    ".join(projected)
        ctes.append(
            f"{_quote(current_alias)} AS (\n"
            f"  SELECT\n    {select_list}\n"
            f"  FROM {_quote(previous_alias)} AS source\n"
            ")"
        )
        previous_alias = current_alias

    destination = config.writer.destination
    project = destination.project or default_project
    if project is None:
        raise PipelineCompileError(
            f"Target node {target_node_id!r} must set destination.project for compilation"
        )
    query = (
        "WITH\n"
        + ",\n".join(ctes)
        + f"\nSELECT {', '.join(_quote(field.name) for field in target.fields)}\n"
        + f"FROM {_quote(previous_alias)}"
    )
    return CompiledTarget(
        node_id=target_node_id,
        query=query,
        write_mode=config.writer.write_mode,
        target=WriteTarget(
            project=project,
            dataset=destination.dataset,
            table=destination.table,
            business_key=tuple(destination.business_key),
        ),
    )


def prepare_target_writer(
    target_node: Node,
    *,
    default_project: str,
    client: object | None = None,
) -> PreparedTargetWriter:
    """Resolve target-node configuration to one concrete BigQuery writer."""
    config = target_node.config
    if target_node.type != "target" or not isinstance(config, TargetNodeConfig):
        raise PipelineCompileError(f"Node {target_node.id!r} is not a configured target")
    if config.writer is None:
        raise PipelineCompileError(f"Target node {target_node.id!r} has no writer configuration")
    writer_config = config.writer
    destination = writer_config.destination
    project = destination.project or default_project
    typed_client = cast("_BigQueryClient | None", client)
    match writer_config.write_mode:
        case WriteMode.SCD1:
            writer: WritePattern = BigQueryScd1Writer(project=project, client=typed_client)
        case WriteMode.SCD2:
            writer = BigQueryScd2Writer(project=project, client=typed_client)
        case WriteMode.INCREMENTAL:
            assert writer_config.cursor_field is not None
            writer = BigQueryIncrementalWriter(
                project=project,
                cursor_field=writer_config.cursor_field,
                client=typed_client,
            )
        case WriteMode.SNAPSHOT:
            partitioning = writer_config.partitioning
            if partitioning is None or partitioning.field is None:
                raise PipelineCompileError(
                    "Snapshot target execution requires field-based partitioning"
                )
            writer = BigQuerySnapshotWriter(
                project=project,
                snapshot_field=partitioning.field,
                client=typed_client,
            )
        case WriteMode.REPLACE:
            writer = BigQueryReplaceWriter(project=project, client=typed_client)
    return PreparedTargetWriter(
        writer=writer,
        target=WriteTarget(
            project=project,
            dataset=destination.dataset,
            table=destination.table,
            business_key=tuple(destination.business_key),
        ),
    )


def _compile_mapping(mapping: FieldMapping, cast_to: str | None, *, alias: str) -> str:
    transformation = mapping.transformation
    if transformation is None or transformation.kind is TransformationKind.DIRECT:
        if mapping.source is None:
            raise PipelineCompileError("A direct mapping must name its source field")
        expression = f"{alias}.{_quote(mapping.source)}"
    elif transformation.kind is TransformationKind.CONSTANT:
        expression = exp.convert(transformation.constant).sql(dialect="bigquery")
    elif transformation.kind is TransformationKind.EXPRESSION:
        expression = _compile_expression(transformation, alias=alias)
    else:
        expression = _compile_custom(transformation, alias=alias)
    if cast_to is not None:
        if not _TYPE.fullmatch(cast_to):
            raise PipelineCompileError(f"Unsupported target cast type {cast_to!r}")
        expression = f"SAFE_CAST({expression} AS {cast_to.upper()})"
    return f"{expression} AS {_quote(mapping.target)}"


def _compile_source_field(field: NodeField) -> str:
    column = _quote(field.name)
    if field.cast_to is None:
        return column
    if not _TYPE.fullmatch(field.cast_to):
        raise PipelineCompileError(f"Unsupported source cast type {field.cast_to!r}")
    return f"SAFE_CAST({column} AS {field.cast_to.upper()}) AS {column}"


def _compile_expression(transformation: Transformation, *, alias: str) -> str:
    assert transformation.expression is not None
    try:
        parsed = sqlglot.parse_one(transformation.expression, read="bigquery")
    except sqlglot.errors.ParseError as error:
        raise PipelineCompileError("Transformation expression is not valid BigQuery SQL") from error
    if isinstance(parsed, (exp.Query, exp.Subquery)) or any(
        isinstance(node, (exp.Query, exp.Subquery, exp.Table, exp.Star, exp.Parameter))
        for node in parsed.walk()
    ):
        raise PipelineCompileError("Transformation expressions must be scalar and row-local")
    declared = set(transformation.inputs)
    referenced = {column.name for column in parsed.find_all(exp.Column)}
    if referenced != declared:
        raise PipelineCompileError(
            "Transformation expression columns must exactly match its declared inputs"
        )
    for function in parsed.find_all(exp.Func):
        name = function.sql_name().upper()
        if name == "TRY_CAST":
            name = "SAFE_CAST"
        if name not in _ALLOWED_FUNCTIONS:
            raise PipelineCompileError(f"SQL function {name!r} is not allow-listed")
    qualified = parsed.transform(
        lambda node: exp.column(node.name, table=alias) if isinstance(node, exp.Column) else node
    )
    return qualified.sql(dialect="bigquery")


def _compile_custom(transformation: Transformation, *, alias: str) -> str:
    inputs = [f"{alias}.{_quote(name)}" for name in transformation.inputs]
    arguments = [
        exp.convert(value).sql(dialect="bigquery") for value in transformation.arguments.values()
    ]
    values = [*inputs, *arguments]
    match transformation.function:
        case "transforms.lower":
            _require_arity(transformation.function, values, 1)
            return f"LOWER({values[0]})"
        case "transforms.upper":
            _require_arity(transformation.function, values, 1)
            return f"UPPER({values[0]})"
        case "transforms.trim":
            _require_arity(transformation.function, values, 1)
            return f"TRIM({values[0]})"
        case "transforms.normalize_phone":
            if len(inputs) != 1:
                raise PipelineCompileError(
                    "Custom transform 'transforms.normalize_phone' requires one input"
                )
            if transformation.arguments:
                raise PipelineCompileError(
                    "Custom transform 'transforms.normalize_phone' does not accept arguments"
                )
            return f"REGEXP_REPLACE(CAST({inputs[0]} AS STRING), r'[^0-9+]', '')"
        case _:
            raise PipelineCompileError(
                f"Custom transform {transformation.function!r} is not allow-listed"
            )


def _require_arity(function: str | None, values: list[str], count: int) -> None:
    if len(values) != count:
        raise PipelineCompileError(f"Custom transform {function!r} requires {count} argument")


def _quote(identifier: str) -> str:
    if not _IDENTIFIER.fullmatch(identifier):
        raise PipelineCompileError(f"Unsafe BigQuery identifier {identifier!r}")
    return f"`{identifier}`"
