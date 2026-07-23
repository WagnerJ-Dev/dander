"""Declarative pipeline-graph model and its YAML/JSON serialization.

A pipeline graph is the durable, declarative primitive behind both a future drag-drop UI and
fully code-authored pipelines: a list of ``nodes`` (data objects/tasks) and a list of ``edges``
(how they connect). This module owns the model **shape** and stable round-trip serialization
only — uniqueness checks, dangling-edge detection, self-loops, DAG/cycle detection, adjacency,
and topological ordering are deliberately out of scope here (see DANDER-3, which builds on these
models).
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from pathlib import Path


class NodeField(BaseModel):
    """A single declared field on a node's schema.

    Describes the shape of one field a node exposes (e.g. one column of a `source` node) —
    never a value. This model carries structural/descriptive metadata only; cross-node
    validation that mappings/joins reference real declared fields is deferred (see DANDER-8).

    Attributes:
        name: Required identifier for the field.
        type: Free-form type token (e.g. a BigQuery-ish ``STRING``/``INT64``). Validation of
            accepted values is deferred, mirroring how `Node.type` is handled.
        nullable: Whether the field may be null. Defaults to `True` since most source fields
            are nullable; set `False` to opt into a not-null guarantee.
        description: Optional human-readable documentation for the field.
        metadata: Free-form tags/labels only (e.g. a `sensitivity`/`pii` classification,
            ownership). Per `steering/01-security.md`, this must never hold a real field value
            or sample data — labels/tags only.
    """

    name: str
    type: str
    nullable: bool = True
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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
        fields: Ordered field schema the node produces (e.g. the columns a `source` node
            exposes). Defaults to empty — a node with no declared fields loads and dumps just
            as a DANDER-2 node did. Cross-node validation of field references is deferred to
            DANDER-8.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    name: str
    config: dict[str, Any] = Field(
        default_factory=dict, validation_alias=AliasChoices("config", "params")
    )
    fields: list[NodeField] = Field(default_factory=list)


class TransformationKind(StrEnum):
    """The closed set of transformation kinds a `Transformation` may declare.

    A `StrEnum` (not a bare `Literal`) so the Transform/Writer layer and DANDER-8 can branch on a
    named, importable type, while it still serializes to/from its plain string value stably in
    YAML and JSON. Extensible by adding a member later without touching callers.

    Attributes:
        DIRECT: A plain field-to-field copy — no expression, no constant.
        EXPRESSION: The target value is computed by an opaque, declarative expression string.
        CONSTANT: The target value is a fixed literal, independent of any source field.
    """

    DIRECT = "direct"
    EXPRESSION = "expression"
    CONSTANT = "constant"


class Transformation(BaseModel):
    """A declarative transformation attached to a `FieldMapping`.

    Captures *what kind* of transformation a mapping performs and its declarative payload. This
    model is opaque and inert: an `expression` string is never parsed, compiled, or evaluated
    here, and a `constant` literal is never interpreted — both are stored as-authored for the
    Transform/Writer layer to execute later, per `steering/00-project-overview.md`. Neither an
    `expression` nor a `constant` may embed a secret or credential literal
    (`steering/01-security.md`); a transformation references fields and functions, never values
    that belong in Secret Manager / env.

    Attributes:
        kind: The transformation discriminator. Defaults to `DIRECT` (a plain copy).
        expression: Opaque, declarative expression string for the `EXPRESSION` kind (e.g.
            ``"CONCAT(first_name, ' ', last_name)"``). Never evaluated here. Required and
            non-empty when `kind` is `EXPRESSION`; must be unset otherwise.
        constant: The literal payload for the `CONSTANT` kind. Typed `Any` because a constant is
            arbitrary JSON (str/int/float/bool/null/list/dict), matching the `Node.config`
            precedent. Required (including an explicit `null`) when `kind` is `CONSTANT`; must be
            unset otherwise. Presence — not truthiness — is what is checked, so a legitimate
            constant `null` is distinguishable from "not provided".
        inputs: Zero or more source-field names this transformation references, so a later
            validation pass (DANDER-8) can check they resolve. Names only, never values.
        metadata: Optional free-form tags.
    """

    model_config = ConfigDict(populate_by_name=True)

    kind: TransformationKind = TransformationKind.DIRECT
    expression: str | None = None
    constant: Any = None  # arbitrary JSON literal for the CONSTANT kind; see Attributes above.
    inputs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_kind_payload(self) -> Transformation:
        """Enforce the payload each `kind` requires/forbids.

        The `CONSTANT`-requires-a-literal check uses `model_fields_set` (not truthiness) so an
        authored `constant: null` is distinguishable from an omitted `constant` on first parse.
        The "must not carry a constant" prohibitions for the other kinds instead check
        `self.constant is not None`: `model_dump` always serializes every field (including a
        default `constant: null`), so a `DIRECT`/`EXPRESSION` transformation that round-trips
        through dump -> load would otherwise always show `constant` as "set" on reload and
        spuriously fail this check. A `constant` value of `None` is never meaningful outside the
        `CONSTANT` kind, so checking its value (not its presence) here is lossless.

        Raises:
            ValueError: If `kind` is `EXPRESSION` and `expression` is missing/empty, or
                `constant` has a non-null value; if `kind` is `CONSTANT` and `constant` is not
                present, or `expression` is set; or if `kind` is `DIRECT` and either `expression`
                is set or `constant` has a non-null value.
        """
        if self.kind is TransformationKind.EXPRESSION:
            if self.expression is None or not self.expression.strip():
                raise ValueError(
                    "Transformation(kind=expression) requires a non-empty 'expression'."
                )
            if self.constant is not None:
                raise ValueError("Transformation(kind=expression) must not set 'constant'.")
        elif self.kind is TransformationKind.CONSTANT:
            if "constant" not in self.model_fields_set:
                raise ValueError(
                    "Transformation(kind=constant) requires a 'constant' literal to be set."
                )
            if self.expression is not None:
                raise ValueError("Transformation(kind=constant) must not set 'expression'.")
        else:  # DIRECT
            if self.expression is not None:
                raise ValueError("Transformation(kind=direct) must not set 'expression'.")
            if self.constant is not None:
                raise ValueError("Transformation(kind=direct) must not set 'constant'.")

        return self


class FieldMapping(BaseModel):
    """A single field-to-field lineage mapping on an edge, optionally transformed.

    Column-level lineage for a connection: names the source-node field this mapping reads from
    and the target-node field it writes to, both by their field-name string (the `name`
    identifiers declared via `NodeField` in DANDER-4). By default (`transformation=None`, or an
    explicit `Transformation(kind=DIRECT)`) this is a direct-copy (passthrough/rename/project)
    mapping, matching DANDER-5's behavior unchanged. A `transformation` of kind `EXPRESSION` or
    `CONSTANT` (DANDER-6) attaches declarative transform logic — never evaluated here, only
    stored for the Transform/Writer layer. Validating that `source`/`target`/`transformation.
    inputs` actually exist on the edge's connected nodes is deferred (see DANDER-8).

    Attributes:
        source: The source-node field name this mapping reads from (on-disk key: ``source``).
            `None` for a **derived/computed** target field with no single source column; in that
            case `transformation` (kind `EXPRESSION` or `CONSTANT`) is required to supply the
            logic, and any referenced source fields are named in `transformation.inputs` instead.
        target: The target-node field name this mapping writes to (on-disk key: ``target``).
        transformation: Optional declarative transformation for this mapping. `None` means a
            plain direct copy (DANDER-5 default, backward compatible).
        metadata: Free-form tags/labels only (e.g. a lineage note). Per
            `steering/01-security.md`, this must never hold a real field value or sample data —
            labels/tags only.
    """

    model_config = ConfigDict(populate_by_name=True)

    source: str | None = None
    target: str
    transformation: Transformation | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_derived_mapping_has_transformation(self) -> FieldMapping:
        """Require a transformation when there is no single source field.

        A mapping with `source is None` produces nothing unless it carries the logic to derive
        its value, so it must declare a `transformation` of kind `EXPRESSION` or `CONSTANT`.

        Raises:
            ValueError: If `source` is `None` and `transformation` is missing, or is present but
                not `EXPRESSION`/`CONSTANT` kind.
        """
        if self.source is None and (
            self.transformation is None
            or self.transformation.kind
            not in (TransformationKind.EXPRESSION, TransformationKind.CONSTANT)
        ):
            raise ValueError(
                "FieldMapping with source=None (a derived field) requires a "
                "transformation of kind 'expression' or 'constant'."
            )
        return self


class JoinType(StrEnum):
    """The closed set of join kinds a `JoinSpec` may declare.

    A `StrEnum` (not a bare `Literal`), matching the established convention in `writer/base.py`
    (`WriteMode`) and `transform/model.py` (`Materialization`) — it gives a named, importable
    type for the Transform layer to branch on later while serializing to/from a plain string
    value stably in YAML and JSON. An out-of-set value fails validation with a clear error.

    Attributes:
        INNER: Only rows with matching keys on both sides.
        LEFT: All rows from the left (edge `from`) side; unmatched right-side fields are null.
        RIGHT: All rows from the right (edge `to`) side; unmatched left-side fields are null.
        FULL: All rows from both sides; unmatched fields on either side are null.
    """

    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    FULL = "full"


class JoinKeyPair(BaseModel):
    """One equality key pairing in a `JoinSpec`.

    Pairs a field name on the join's left side with a field name on its right side. Referenced
    strictly **by field name**, never by value (`steering/01-security.md`). Field-existence
    checks (whether these names resolve on the joined nodes) are deferred to DANDER-8.

    Attributes:
        left: Field name on the edge's **from** node (the join's left side; see `JoinSpec` and
            `Edge.join` for the left/right orientation).
        right: Field name on the edge's **to** node (the join's right side).
    """

    model_config = ConfigDict(populate_by_name=True)

    left: str
    right: str


class JoinSpec(BaseModel):
    """A declarative join specification on a connection that combines two sources.

    Names the join **type** and the ordered equality key pairs used to combine an edge's two
    endpoints. This model is opaque and inert: no SQL is generated and no join is executed here
    — it records join *intent* only, for the Transform layer to execute later
    (`steering/00-project-overview.md`). Cross-node validation that the key-pair field names
    exist on the joined nodes is deferred to DANDER-8.

    **Left/right orientation:** the join's left side is always the edge's `from` node
    (`Edge.source`) and the right side is always the edge's `to` node (`Edge.target`). Each
    `JoinKeyPair` pairs a field on the left (`from`) node with a field on the right (`to`) node.
    *Left*/*right* is used here (rather than *source*/*target*) deliberately: on `Edge`,
    `source`/`target` already name node **ids**, while here we name field **names** on those
    nodes — keeping the vocabularies distinct avoids conflating the two meanings.

    Attributes:
        type: The join kind — one of `JoinType`'s closed set. Invalid values raise a
            `ValidationError` at the Pydantic boundary.
        keys: Ordered equality key pairs; at least one is required (an empty list raises a
            `ValidationError`). Declaration order is preserved.
        metadata: Free-form tags/labels only (never data/secrets), consistent with
            `Edge.metadata` / `Node.config`.
    """

    model_config = ConfigDict(populate_by_name=True)

    type: JoinType
    keys: list[JoinKeyPair] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


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
        mappings: Ordered field-to-field lineage across this connection. Defaults to empty — an
            edge with no mappings loads and dumps just as a DANDER-2/DANDER-4 edge did.
            Cross-node validation that a mapping's `source`/`target` field names exist on the
            connected nodes is deferred to DANDER-8.
        join: Optional declarative join specification for a connection that combines two
            sources. `None` (the default) means a plain edge with no join — unchanged and
            backward compatible with DANDER-2/4/5 graphs. When present, the join's left side is
            this edge's `source` (`from`) node and its right side is this edge's `target` (`to`)
            node; see `JoinSpec` for the full orientation contract. No cross-node field-existence
            validation happens here (see DANDER-8).
    """

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    metadata: dict[str, Any] = Field(default_factory=dict)
    mappings: list[FieldMapping] = Field(default_factory=list)
    join: JoinSpec | None = Field(default=None)


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


def _dump_graph_payload(graph: PipelineGraph) -> dict[str, Any]:
    """Build the on-disk payload dict for a graph, omitting only join-less `join` keys.

    Backing helper shared by `dump_graph_to_yaml`/`dump_graph_to_json`. A plain
    `graph.model_dump(by_alias=True, mode="json")` would already emit a `join: null` entry for
    every edge with no join (backward-incompatible with DANDER-2/4/5 graphs). A graph-wide
    `exclude_none=True` fixes that but is too blunt: it also drops other, *meaningful* `None`
    values elsewhere in the graph — notably an authored `constant: null` on a `CONSTANT`
    `Transformation`, which then fails to reload (`Transformation(kind=constant) requires a
    'constant' literal to be set`). So the omission is scoped here, after the fact, to exactly
    the `join` key of edges whose `Edge.join` is `None` — every other field, including other
    `None`s, is left untouched.

    Args:
        graph: The graph to serialize.

    Returns:
        A plain JSON-compatible dict (nested dicts/lists/primitives) ready for `yaml.safe_dump`
        or `json.dumps`, with a join-less edge's `join` key absent rather than `null`.
    """
    payload = graph.model_dump(by_alias=True, mode="json")
    for edge, dumped_edge in zip(graph.edges, payload["edges"], strict=True):
        if edge.join is None:
            dumped_edge.pop("join", None)
    return payload


def dump_graph_to_yaml(graph: PipelineGraph, path: Path) -> None:
    """Dump a `PipelineGraph` to a YAML file.

    Edges are serialized with the `from`/`to` keys (never `source`/`target`), matching the
    decided on-disk format. A join-less edge omits its `join` key entirely (see
    `_dump_graph_payload`); no other `None` value anywhere in the graph is dropped — in
    particular an authored `constant: null` on a `CONSTANT` transformation is preserved.

    Args:
        graph: The graph to serialize.
        path: Destination file path; overwritten if it already exists.
    """
    payload = _dump_graph_payload(graph)
    path.write_text(yaml.safe_dump(payload, sort_keys=False))


def dump_graph_to_json(graph: PipelineGraph, path: Path, *, indent: int = 2) -> None:
    """Dump a `PipelineGraph` to a JSON file.

    Edges are serialized with the `from`/`to` keys (never `source`/`target`), matching the
    decided on-disk format. A join-less edge omits its `join` key entirely (see
    `_dump_graph_payload`); no other `None` value anywhere in the graph is dropped — in
    particular an authored `constant: null` on a `CONSTANT` transformation is preserved.

    Args:
        graph: The graph to serialize.
        path: Destination file path; overwritten if it already exists.
        indent: JSON indentation width.
    """
    payload = _dump_graph_payload(graph)
    path.write_text(json.dumps(payload, indent=indent))
