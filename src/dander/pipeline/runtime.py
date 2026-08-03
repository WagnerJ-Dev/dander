"""Execution bridge from a validated PipelineGraph to configured connectors and BigQuery."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Protocol, cast
from uuid import uuid4

import yaml
from google.cloud import bigquery
from pydantic import ValidationError

from dander._bigquery_retry import run_mutation_with_retry
from dander.concurrency import fenced_dml, fencing_job_config
from dander.pipeline.compiler import (
    CompiledTarget,
    PipelineCompileError,
    compile_target,
    prepare_target_writer,
)
from dander.pipeline.errors import GraphValidationError
from dander.pipeline.graph_ops import validate_field_wiring
from dander.pipeline.node_config import SourceNodeConfig, TargetNodeConfig
from dander.transform import TransformRunResult
from dander.writer import BigQueryWriteError, WriteMode

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from dander.concurrency import OwnershipGuard
    from dander.ingestion import SourceConfig
    from dander.pipeline.graph import Node, PipelineGraph

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CONNECTOR = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_PROJECT = re.compile(r"^[A-Za-z][A-Za-z0-9-]{4,61}[A-Za-z0-9]$")


class GraphRuntimeError(RuntimeError):
    """Raised when an authored graph cannot execute through the supported runtime slice."""


def load_graph_for_execution(path: Path) -> PipelineGraph:
    """Load one YAML/JSON graph with strict unknown-field rejection."""
    from dander.pipeline.graph import PipelineGraph

    try:
        text = path.read_text(encoding="utf-8")
        raw = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
        return PipelineGraph.model_validate(raw, extra="forbid")
    except (OSError, json.JSONDecodeError, yaml.YAMLError, ValidationError) as error:
        raise GraphRuntimeError(f"Graph file is invalid: {path.name}") from error


class _QueryJob(Protocol):
    def result(self) -> object:
        """Wait for BigQuery completion."""


class _BigQueryClient(Protocol):
    def query(
        self,
        query: str,
        *,
        job_config: bigquery.QueryJobConfig | None = None,
    ) -> _QueryJob:
        """Submit BigQuery Standard SQL."""

    def delete_table(self, table: str, *, not_found_ok: bool = False) -> None:
        """Delete one run-scoped staging table."""


@dataclass(frozen=True)
class GraphSourceBindings:
    """Resolved graph-source nodes for one existing connector configuration."""

    connector: str
    endpoint_names: tuple[str, ...]
    source_relations: Mapping[str, str]


@dataclass(frozen=True)
class GraphExecutionPlan:
    """Credential-free executable graph plan."""

    bindings: GraphSourceBindings
    targets: tuple[CompiledTarget, ...]


def plan_graph_execution(
    graph: PipelineGraph,
    source_config: SourceConfig,
    *,
    project: str,
    dataset: str,
) -> GraphExecutionPlan:
    """Bind graph sources to connector endpoints and compile every executable target."""
    try:
        validate_field_wiring(graph)
    except GraphValidationError as error:
        raise GraphRuntimeError(str(error)) from error
    if not _PROJECT.fullmatch(project):
        raise GraphRuntimeError("Graph execution requires a valid GCP project id")
    if not _IDENTIFIER.fullmatch(dataset):
        raise GraphRuntimeError("Graph execution requires a valid BigQuery raw dataset id")
    unsupported = sorted({node.type for node in graph.nodes} - {"source", "transform", "target"})
    if unsupported:
        raise GraphRuntimeError(f"Graph execution does not support node type {unsupported[0]!r}")
    if any(field.tests for node in graph.nodes for field in node.fields):
        raise GraphRuntimeError("Graph field tests are not executable yet")

    endpoints = {endpoint.name: endpoint for endpoint in source_config.endpoints}
    endpoint_names: list[str] = []
    relations: dict[str, str] = {}
    for node in graph.nodes:
        if node.type != "source":
            continue
        config = node.config
        if not isinstance(config, SourceNodeConfig):
            raise GraphRuntimeError(f"Source node {node.id!r} has invalid configuration")
        if config.model_extra:
            raise GraphRuntimeError(f"Source node {node.id!r} has unsupported configuration")
        if config.request is not None:
            raise GraphRuntimeError(
                f"Source node {node.id!r} must use its connector endpoint, not an inline request"
            )
        if config.connector is None or config.endpoint is None:
            raise GraphRuntimeError(f"Source node {node.id!r} must declare connector and endpoint")
        if not _CONNECTOR.fullmatch(config.connector) or not _IDENTIFIER.fullmatch(config.endpoint):
            raise GraphRuntimeError(
                f"Source node {node.id!r} has an invalid connector or endpoint binding"
            )
        if config.connector != source_config.name:
            raise GraphRuntimeError(
                f"Source node {node.id!r} must bind to pipeline connector {source_config.name!r}"
            )
        endpoint = endpoints.get(config.endpoint)
        if endpoint is None:
            raise GraphRuntimeError(
                f"Source node {node.id!r} references unknown endpoint {config.endpoint!r}"
            )
        declared = {field.name for field in endpoint.raw_schema}
        if missing := sorted({field.name for field in node.fields} - declared):
            raise GraphRuntimeError(
                f"Source node {node.id!r} references undeclared endpoint field {missing[0]!r}"
            )
        if node.cursor is not None and node.cursor.field != endpoint.incremental_cursor:
            raise GraphRuntimeError(
                f"Source node {node.id!r} cursor does not match its connector endpoint"
            )
        if config.endpoint not in endpoint_names:
            endpoint_names.append(config.endpoint)
        relations[node.id] = f"{project}.{dataset}.{source_config.name}_{config.endpoint}"

    if not relations:
        raise GraphRuntimeError("Graph execution requires at least one source node")

    target_nodes = [node for node in graph.nodes if node.type == "target"]
    if not target_nodes:
        raise GraphRuntimeError("Graph execution requires at least one target node")
    targets: list[CompiledTarget] = []
    for node in target_nodes:
        if not isinstance(node.config, TargetNodeConfig) or node.config.writer is None:
            raise GraphRuntimeError(f"Target node {node.id!r} must declare writer configuration")
        try:
            compiled = compile_target(
                graph,
                node.id,
                source_relations=relations,
                default_project=project,
            )
        except PipelineCompileError as error:
            raise GraphRuntimeError(str(error)) from error
        if compiled.write_mode is not WriteMode.REPLACE:
            raise GraphRuntimeError(
                f"Target node {node.id!r} uses unsupported graph write mode "
                f"{compiled.write_mode.value!r}; use 'replace'"
            )
        try:
            _validate_target(node, compiled, project)
        except (BigQueryWriteError, PipelineCompileError) as error:
            raise GraphRuntimeError(str(error)) from error
        targets.append(compiled)
    return GraphExecutionPlan(
        bindings=GraphSourceBindings(
            connector=source_config.name,
            endpoint_names=tuple(endpoint_names),
            source_relations=relations,
        ),
        targets=tuple(targets),
    )


class BigQueryGraphRunner:
    """Materialize compiled graph targets inside PipelineExecutor's transform stage."""

    def __init__(
        self,
        *,
        plan: GraphExecutionPlan,
        project: str,
        client: _BigQueryClient | None = None,
    ) -> None:
        self._plan = plan
        self._project = project
        self._client = client or cast("_BigQueryClient", bigquery.Client(project=project))

    def build(
        self,
        _models_dir: Path,
        *,
        selected: Iterable[str] | None = None,
        ownership: OwnershipGuard | None = None,
    ) -> TransformRunResult:
        """Stage and transactionally publish selected replace-mode targets."""
        selected_ids = set(selected) if selected is not None else None
        known = {target.node_id for target in self._plan.targets}
        if selected_ids is not None and (unknown := sorted(selected_ids - known)):
            raise GraphRuntimeError(f"Unknown graph target: {unknown[0]!r}")
        targets = tuple(
            target
            for target in self._plan.targets
            if selected_ids is None or target.node_id in selected_ids
        )
        if not targets:
            raise GraphRuntimeError("Graph execution selected no targets")
        for target in targets:
            self._materialize(target, ownership=ownership)
        return TransformRunResult(
            models=tuple(target.node_id for target in targets),
            assertions=0,
        )

    def _materialize(
        self,
        compiled: CompiledTarget,
        *,
        ownership: OwnershipGuard | None,
    ) -> None:
        target = compiled.target
        target_id = f"{target.project}.{target.dataset}.{target.table}"
        staging_id = f"{target.project}.{target.dataset}._dander_stage_{target.table}_{uuid4().hex}"
        columns = tuple(field.name for field in target.schema)
        quoted_columns = ", ".join(f"`{column}`" for column in columns)
        try:
            if ownership is not None:
                ownership.verify()
            self._client.query(
                f"CREATE TABLE `{staging_id}`\n"
                "OPTIONS (expiration_timestamp="
                "TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 1 DAY))\n"
                f"AS\n{compiled.query}"
            ).result()
            self._client.query(
                f"CREATE TABLE IF NOT EXISTS `{target_id}` AS "
                f"SELECT {quoted_columns} FROM `{staging_id}` WHERE FALSE"
            ).result()
            if ownership is not None:
                ownership.verify()
            replacement = (
                f"DELETE FROM `{target_id}` WHERE TRUE;\n"
                f"INSERT INTO `{target_id}` ({quoted_columns})\n"
                f"SELECT {quoted_columns} FROM `{staging_id}`"
            )
            fence = ownership.fence if ownership is not None else None
            if fence is not None:
                script = fenced_dml(replacement, fence)
                job_config = fencing_job_config(fence)
                run_mutation_with_retry(partial(self._client.query, script, job_config=job_config))
            else:
                script = f"BEGIN TRANSACTION;\n{replacement};\nCOMMIT TRANSACTION;"
                run_mutation_with_retry(partial(self._client.query, script))
        finally:
            self._client.delete_table(staging_id, not_found_ok=True)


def _validate_target(node: Node, compiled: CompiledTarget, project: str) -> None:
    """Reuse writer dispatch validation without constructing credentials or performing I/O."""
    prepare_target_writer(node, default_project=project, client=object())
    target = compiled.target
    if target.project != project:
        raise GraphRuntimeError(f"Target node {node.id!r} must write inside the runtime project")
    if not _IDENTIFIER.fullmatch(target.dataset) or not _IDENTIFIER.fullmatch(target.table):
        raise GraphRuntimeError(f"Target node {node.id!r} has an invalid destination")
    columns = [field.name for field in target.schema]
    if not columns or any(not _IDENTIFIER.fullmatch(column) for column in columns):
        raise GraphRuntimeError(f"Target node {node.id!r} must declare valid output fields")
    if len(columns) != len(set(columns)):
        raise GraphRuntimeError(f"Target node {node.id!r} has duplicate output fields")
