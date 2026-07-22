"""Declarative pipeline-graph model and its YAML/JSON serialization.

A pipeline graph is the durable, declarative primitive behind both a future drag-drop UI and
fully code-authored pipelines: a list of ``nodes`` (data objects/tasks) and a list of ``edges``
(how they connect). This module owns the model **shape** and stable round-trip serialization
only — uniqueness checks, dangling-edge detection, self-loops, DAG/cycle detection, adjacency,
and topological ordering are deliberately out of scope here (see DANDER-3, which builds on these
models).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from pathlib import Path


class Node(BaseModel):
    """A single node in a pipeline graph (a data object or task).

    Attributes:
        id: Unique identifier for this node within its graph. Uniqueness is *not* enforced
            here (see DANDER-3).
        type: Node kind, e.g. ``source``/``transform``/``target``/``task``. Kept as a free
            string rather than a closed enum since validation of accepted values is deferred
            to DANDER-3.
        name: Human-readable label.
        config: Free-form node-specific data. Accepts either the ``config`` or ``params`` key
            on load (both map to this one attribute); dumps under the canonical ``config`` key.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    name: str
    config: dict[str, Any] = Field(
        default_factory=dict, validation_alias=AliasChoices("config", "params")
    )


class Edge(BaseModel):
    """A directed connection between two node ids.

    The on-disk/API keys are the reserved words ``from``/``to``; since ``from`` cannot be a
    Python attribute name, this model exposes the Python-safe attributes ``source``/``target``
    and maps them to ``from``/``to`` via Pydantic field aliases. Both by-alias and by-attribute-
    name population work; dumps always emit the ``from``/``to`` aliases.

    Attributes:
        source: The originating node id (on-disk key: ``from``).
        target: The destination node id (on-disk key: ``to``).
        metadata: Optional free-form edge metadata.
    """

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineGraph(BaseModel):
    """The full pipeline graph: a named collection of nodes and edges.

    Attributes:
        name: Human-readable graph name.
        nodes: The graph's nodes.
        edges: The graph's edges.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


def load_graph_from_yaml(path: Path) -> PipelineGraph:
    """Load a `PipelineGraph` from a YAML file.

    Args:
        path: Path to a YAML file containing a `nodes:`/`edges:` document.

    Returns:
        The parsed `PipelineGraph`.
    """
    raw = yaml.safe_load(path.read_text())
    return PipelineGraph.model_validate(raw)


def load_graph_from_json(path: Path) -> PipelineGraph:
    """Load a `PipelineGraph` from a JSON file.

    Args:
        path: Path to a JSON file containing a `nodes:`/`edges:` document.

    Returns:
        The parsed `PipelineGraph`.
    """
    return PipelineGraph.model_validate_json(path.read_text())


def dump_graph_to_yaml(graph: PipelineGraph, path: Path) -> None:
    """Dump a `PipelineGraph` to a YAML file.

    Edges are serialized with the `from`/`to` keys (never `source`/`target`), matching the
    decided on-disk format.

    Args:
        graph: The graph to serialize.
        path: Destination file path; overwritten if it already exists.
    """
    payload = graph.model_dump(by_alias=True, mode="json")
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


def dump_graph_to_json(graph: PipelineGraph, path: Path, *, indent: int = 2) -> None:
    """Dump a `PipelineGraph` to a JSON file.

    Edges are serialized with the `from`/`to` keys (never `source`/`target`), matching the
    decided on-disk format.

    Args:
        graph: The graph to serialize.
        path: Destination file path; overwritten if it already exists.
        indent: JSON indentation width.
    """
    path.write_text(graph.model_dump_json(by_alias=True, indent=indent))
