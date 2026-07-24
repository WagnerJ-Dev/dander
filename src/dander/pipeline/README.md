# `dander.pipeline`

## Role

`dander.pipeline` owns the **declarative pipeline graph** — the durable primitive behind both a
future drag-drop UI and fully code-authored pipelines. A graph is a list of `nodes` (data objects /
tasks) and `edges` (connections between them, i.e. how data flows). This package does **not**
execute anything: it defines the on-disk shape (YAML/JSON), validates that a graph is structurally
and semantically sound, and derives read-only structure (adjacency, topological order) from it.
Execution — expression evaluation, join/SQL generation, ingestion, materialization — happens in the
Ingestion/Transform/Writer layers described in the module map in
`steering/00-project-overview.md`; the graph only records *intent*.

This doc is accurate to the pipeline package as merged. If the code and this doc ever disagree, the
code is right and this doc has drifted — please fix it.

## Package layout

| Module | Responsibility |
|---|---|
| `dander.pipeline.graph` | The model: `Node`, `NodeField`, `Edge`, `FieldMapping`, `Transformation`, `JoinSpec`, `CursorStrategy`, `PipelineGraph`, and YAML/JSON load/dump. Pure value objects — no validation logic beyond Pydantic's own boundary constraints. |
| `dander.pipeline.graph_ops` | The correctness layer: structural `validate`, `topological_order`, `AdjacencyIndex`, and field-wiring `validate_field_wiring`. Pure functions of a `PipelineGraph` — nothing is persisted onto the model. |
| `dander.pipeline.node_config` | The discriminated, per-node-type `Node.config` models — `NodeType`, `NodeConfig`, `SourceNodeConfig`, `TransformNodeConfig`, `TargetNodeConfig` — and the routing function `Node` delegates to. See *Typed per-node-type config* below. |
| `dander.pipeline.request_spec` | `SourceNodeConfig`'s declarative request/payload spec — `HttpMethod`, `RequestSpec` — and the secret/field-reference grammar its header/param/body values must follow. See *Source request/payload spec* below. |
| `dander.pipeline.errors` | The typed `GraphValidationError` hierarchy raised by `graph_ops`. |

### Import paths (what's actually exported where)

The package `__init__.py` (`dander.pipeline`) re-exports the graph shape (`Node`, `Edge`,
`PipelineGraph`, the four `load_*`/`dump_*` functions), the `graph_ops` functions
(`validate`, `validate_field_wiring`, `topological_order`, `AdjacencyIndex`), the full `errors`
hierarchy, and the typed node-config classes (`NodeType`, `NodeConfig`, `SourceNodeConfig`,
`TransformNodeConfig`, `TargetNodeConfig`, `HttpMethod`, `RequestSpec`). **It does not currently
re-export the finer-grained model classes** — `NodeField`, `FieldMapping`, `Transformation`,
`TransformationKind`, `JoinSpec`, `JoinKeyPair`, `JoinType`, `CursorStrategy`, `CursorKind` —
those must be imported from the submodule directly:

```python
from dander.pipeline import Node, Edge, PipelineGraph, validate, validate_field_wiring
from dander.pipeline import SourceNodeConfig, HttpMethod, RequestSpec
from dander.pipeline.graph import NodeField, FieldMapping, Transformation, TransformationKind
from dander.pipeline.graph import JoinSpec, JoinKeyPair, JoinType
from dander.pipeline.graph import CursorStrategy, CursorKind
from dander.pipeline.errors import DuplicateFieldNameError, UnknownFieldReferenceError
```

(`CursorKind`/`CursorStrategy` follow the same asymmetry as the rest of this list — see the note
below.)

(See *Implementation Notes* in `tickets/DANDER-9-pipeline-fields-mappings-docs.md` for a note on
this asymmetry.)

## Node field schema

A `Node` may declare an ordered `fields: list[NodeField]` — the schema it exposes (e.g. the columns
a `source` node produces). It defaults to empty, so a fieldless node is unchanged from the original
`Node`/`Edge` shape. Each `NodeField` has:

| Key | Meaning |
|---|---|
| `name` | Required identifier for the field. |
| `type` | Free-form type token (e.g. a BigQuery-ish `STRING`/`INT64`). Not yet validated against a closed set — same treatment as `Node.type`. |
| `nullable` | Whether the field may be null. Defaults to `true`. |
| `description` | Optional human-readable documentation. |
| `metadata` | Free-form dict, default `{}`. **Tags/labels only** (e.g. a `sensitivity`/`pii` classification) — never a real field value or sample data (`steering/01-security.md`). |

## Connection field-to-field mapping

An `Edge` may declare an ordered `mappings: list[FieldMapping]` — column-level lineage across the
connection. Each `FieldMapping` is:

| Key | Meaning |
|---|---|
| `source` | The source-node field **name** this mapping reads from. `None` for a derived/computed target with no single source column — in that case a `transformation` of kind `expression` or `constant` is required. |
| `target` | The target-node field **name** this mapping writes to. Always required. |
| `transformation` | Optional; see below. `None` means a plain direct copy. |
| `metadata` | Free-form tags/labels only, default `{}`. |

Both `source` and `target` reference fields **by name**, never by value. Whether those names
actually resolve on the edge's connected nodes is a *validation-layer* concern (below), not
something `FieldMapping` itself checks.

## Connection transformations

A `FieldMapping` may carry a `transformation: Transformation | None`. A `Transformation` is
**opaque and inert** — an `expression` string is never parsed or evaluated here, and a `constant`
literal is never interpreted; both are stored as-authored for the Transform/Writer layer to execute
later. Neither may embed a secret or credential — a transformation references fields and functions,
never values that belong in Secret Manager / env (`steering/01-security.md`).

`kind: TransformationKind` is a closed `StrEnum` with three values:

| Kind | Payload |
|---|---|
| `direct` (default) | No `expression`, no `constant` — a plain field copy. |
| `expression` | Requires a non-empty `expression` string (e.g. `"UPPER(full_name)"`); `constant` must be unset. |
| `constant` | Requires an explicit `constant` literal to be **set** (including `null` — presence, not truthiness, is checked, so a legitimate constant `null` is distinguishable from "not provided"); `expression` must be unset. |

`inputs: list[str]` names zero or more source-field names the transformation references (checked
downstream by field-wiring validation, not by the model itself). `metadata` is free-form tags only.

## Join specification

An `Edge` may carry an optional `join: JoinSpec | None` for a connection that **combines two
sources**. `None` (the default) is a plain edge, unchanged and backward-compatible with graphs that
predate joins. `JoinSpec` is opaque and inert: **no SQL is generated and no join is executed here**
— it records join *intent* for the Transform layer.

- `type: JoinType` — a closed `StrEnum`: `inner`, `left`, `right`, `full`. An out-of-set value fails
  Pydantic validation.
- `keys: list[JoinKeyPair]` — ordered equality key pairs; **at least one is required** (an empty
  list raises a `ValidationError`). Declaration order is preserved.
- `metadata` — free-form tags only.

**Left/right orientation:** the join's left side is always the edge's `from` node (`Edge.source`)
and the right side is always the edge's `to` node (`Edge.target`). Each `JoinKeyPair` pairs a
`left` field name (on the `from` node) with a `right` field name (on the `to` node). *Left*/*right*
is used for field names deliberately, to avoid colliding with `source`/`target`, which already name
node **ids** on `Edge`.

*(Product note: representing join semantics on the graph — vs. leaving joins entirely to the
Transform layer — was a genuine fork; the graph took the in-scope, declarative interpretation. See
Implementation Notes below for the Decision Log status of this call.)*

## Node cursor / watermark strategy

A `Node` may carry an optional `cursor: CursorStrategy | None` (DANDER-18) declaring how a
source/ingestion node resumes incrementally. `None` (the default) is a plain node, unchanged and
backward-compatible with graphs that predate cursor strategies. `CursorStrategy` is opaque and
inert: **no state is ever read, written, or persisted here** — it records cursor *intent* only,
for a future Orchestration/State layer to honor (see `dander.state.watermark.WatermarkStore` and
the control-table/idempotency design in `steering/00-project-overview.md` /
`steering/02-engineering.md`).

- `field: str` — the cursor field name the source advances on (e.g. `updated_at`). Referenced by
  name only, never a value. Required and non-empty after stripping (a whitespace-only `field`
  raises a `ValidationError`, same treatment as `Transformation.expression`).
- `kind: CursorKind` — a closed `StrEnum`: `timestamp`, `sequence`, `opaque_token`. An out-of-set
  value fails Pydantic validation. Required — there is no sensible default kind.
- `params` — free-form, kind-specific parameters (e.g. a timestamp format hint). Opaque and inert,
  never interpreted here; never a secret (`steering/01-security.md`).
- `metadata` — free-form tags/labels only, default `{}`.

**Migration from `Endpoint.incremental_cursor`.** Before DANDER-18, `dander.ingestion.source.
Endpoint.incremental_cursor` was the only place a cursor was named — just a field name string,
with no kind and disconnected from the pipeline graph. That field is kept unchanged so existing
connector YAML keeps loading, but it is now documented as the legacy, narrow form that
`Node.cursor` supersedes. `CursorStrategy.from_incremental_cursor(cursor_field: str | None) ->
CursorStrategy | None` is the clean mapping bridge: `None`/empty maps to `None`; a non-empty
string maps to `CursorStrategy(field=cursor_field, kind=CursorKind.TIMESTAMP)`. The `TIMESTAMP`
default is a **documented assumption** (the historical `Source.extract(..., since=...)` contract
treats the cursor as a monotonic "since" bound, which is timestamp-shaped by default) — a legacy
endpoint whose cursor was actually a sequence/token must author an explicit node-level
`CursorStrategy` rather than relying on this helper. The classmethod takes a plain `str | None`
(not an `Endpoint`), so `dander.pipeline` gains no import dependency on `dander.ingestion`.

A cursor-less node omits its `cursor` key entirely on dump (not `cursor: null`), matching the
join-less-`join` omission above.

```yaml
- id: extract_candidates
  type: source
  name: Extract Candidates
  cursor:
    field: updated_at
    kind: timestamp
```

*(Product note: surfacing the cursor strategy on the graph node — vs. leaving it entirely to the
Orchestration/State layer — mirrors the DANDER-7 join-on-the-graph call. See Implementation Notes
below for the Decision Log status of this call.)*

## Typed per-node-type config

`Node.config` is no longer a single opaque `dict` for every node regardless of `type`. It is
routed, by `Node.type`, to a distinct Pydantic model:

| `Node.type` | Config model |
|---|---|
| `source` | `SourceNodeConfig` |
| `transform` | `TransformNodeConfig` |
| `target` | `TargetNodeConfig` |
| anything else (e.g. `task`) | plain `dict` — the pre-DANDER-10 free-form behavior, unchanged |

All three subclass `NodeConfig` (`extra="allow"`, so config content with no dedicated field yet is
preserved losslessly rather than rejected) and are **distinct classes**, so a `source` node's
`config` can never silently be a `TargetNodeConfig` instance (and vice versa) — constructing a
`Node` with a mismatched typed config raises a `ValidationError` naming both class names and the
node's `type`, without echoing any config value. A modeled node with no `config` key loads as an
empty typed model (e.g. `TargetNodeConfig()`), so this is fully backward compatible with
DANDER-2..9 graphs. `SourceNodeConfig` currently carries one dedicated field beyond the inherited
`extra` bucket — `request` — described next; `TransformNodeConfig`/`TargetNodeConfig` remain
open placeholders pending later tickets (transform materialization detail; DANDER-16's
write-pattern/destination-table config).

## Source request/payload spec

A `source` node's `config` may carry an optional `request: RequestSpec | None` describing *how*
it calls its API — the HTTP method, headers, query params, and a request body template. `None`
(the default) is a plain, spec-less GET, unchanged from a pre-DANDER-11 source node; its `request`
key is omitted entirely on dump (not written as `request: null`), matching the join-less-`join`
omission above.

`RequestSpec` is **inert**: nothing in this package sends a request, resolves a secret, or renders
`body` — that happens in the Ingestion layer. Its fields:

| Key | Meaning |
|---|---|
| `method` | One of the closed `HttpMethod` set: `GET` (default) / `POST` / `PUT` / `PATCH` / `DELETE`. |
| `headers` | Request headers, name -> value. |
| `query_params` | Query-string parameters, name -> value. Named `query_params` (not `params`) to avoid colliding with the `config`/`params` alias on `Node`. |
| `body` | A JSON-object body template, a raw string template (e.g. GraphQL), or `None`. |

**Header/query-param/body values are secret references or field references only — never an inline
secret literal** (`steering/01-security.md`). Recognized references (never resolved here):

| Kind | Forms |
|---|---|
| Secret reference | `secret:<name>`, `env:<VAR_NAME>`, or a Secret Manager resource name (`projects/…/secrets/…/versions/…`) — consistent with `SourceConfig.auth_ref` (`dander.ingestion.source`). |
| Field reference | `field:<field_name>` or mustache `{{ <field_name> }}`. |

Two rules enforce this, applied by a `model_validator` on `RequestSpec`:

- **Rule A (deterministic).** A header/param whose *name* is in a documented sensitive set
  (`Authorization`, `Proxy-Authorization`, `X-Api-Key`, `Api-Key`, `X-Auth-Token`, `Cookie`,
  `Set-Cookie` for headers; `api_key`, `access_token`, `token`, `secret`, `client_secret`,
  `password`, and hyphenated variants for query params — all case-insensitive) **must** be a
  recognized reference; a literal there raises a `ValidationError`.
- **Rule B (defense in depth, best-effort).** Any value anywhere — including nested inside
  `body` — that is not a recognized reference and *looks like* a raw credential (an
  `Authorization`-style scheme prefix, a PEM block, a known key prefix like Stripe's `sk_`/AWS's
  `AKIA`/GitHub's `ghp_`/Slack's `xox*`, or a long whitespace-free base64/hex-ish run mixing
  letters and digits) is rejected too. This is a heuristic, not a proof — the guarantee for the
  positions that actually carry credentials is Rule A; Rule B is a tripwire for everywhere else.

Error messages name only the **position** (`header '<name>'`, `query param '<name>'`, or `body`)
and the rule violated — **never the offending value** (`steering/01-security.md`).

```yaml
config:
  endpoint: /candidates
  request:
    method: POST
    headers:
      Authorization: "secret:candidate_source_api_key"   # reference -- Rule A requires this
      Content-Type: "application/json"                    # benign literal -- both rules pass it
    query_params:
      since: "field:updated_since"                        # reference to a declared field
    body:
      query: "field:graphql_query"
      variables:
        candidate_id: "field:candidate_id"
```

`is_secret_reference`, `is_field_reference`, `is_reference`, and `looks_like_raw_credential` are
also exported from `dander.pipeline.request_spec` as standalone, unit-testable pure functions.

## Validation layer

Two tiers, run in a fixed order — structural first, field-wiring second — because field-wiring
checks assume the invariants structural validation guarantees (unique node ids, resolvable edge
endpoints).

### 1. Structural — `graph_ops.validate(graph)`

Four checks, in order:

| Check | Error |
|---|---|
| Node ids unique | `DuplicateNodeIdError` |
| Every edge endpoint references an existing node id | `DanglingEdgeError` |
| No edge is a self-loop | `SelfLoopError` |
| The graph is a DAG (no cycle) | `GraphCycleError` |

`graph_ops.topological_order(graph)` runs `validate` first, then returns node ids in a valid
execution order (every edge's source before its target).

### 2. Field-wiring — `graph_ops.validate_field_wiring(graph)`

Runs `validate` first (so a structural fault always surfaces before a field-wiring fault), then:

| Check | Error |
|---|---|
| No two fields on the same node share a `name` | `DuplicateFieldNameError` |
| Every `FieldMapping.source`/`.target` resolves on the edge's source/target node | `UnknownFieldReferenceError` |
| Every `Transformation.inputs` entry resolves on the edge's source node | `UnknownFieldReferenceError` |
| Every `JoinKeyPair.left`/`.right` resolves on the edge's source(left)/target(right) node | `JoinKeyFieldError` (subclass of `UnknownFieldReferenceError`) |

All of the above subclass `GraphValidationError`, so a caller that just wants "did this graph
validate" can catch that one root type; a caller that wants to distinguish failure modes catches
the specific subclass. **Error messages carry structure only** — node ids, edge endpoint ids, and
field names — and never a node's `config`, a field's/edge's `metadata`, a field value, or a
transformation's `expression`/`constant` payload (`steering/01-security.md`).

## Annotated end-to-end example (YAML)

Fake, non-sensitive names throughout. `crm_contacts` is a source node with two declared fields;
`warehouse_customers` is a target node with two declared fields; the connection between them has a
direct mapping, a derived field driven by an `expression` transformation, and a `left` join keyed
on `contact_id` ↔ `customer_id`.

```yaml
name: crm_to_warehouse_example
nodes:
  # A source node declaring the fields it exposes.
  - id: crm_contacts
    type: source
    name: Extract CRM Contacts
    config:                        # node-specific config; `params` also accepted on load
      endpoint: /contacts
    fields:
      - name: contact_id
        type: STRING
        nullable: false
        description: Unique contact identifier from the CRM.
      - name: full_name
        type: STRING
        description: Contact's full name as entered in the CRM.
        metadata:
          sensitivity: pii          # tag only -- never a real value

  # A target node declaring the fields it accepts.
  - id: warehouse_customers
    type: target
    name: Load Warehouse Customers
    fields:
      - name: customer_id
        type: STRING
        nullable: false
      - name: display_name
        type: STRING

edges:
  - from: crm_contacts               # on-disk key is `from` (Edge.source)
    to: warehouse_customers          # on-disk key is `to` (Edge.target)
    mappings:
      # A plain direct mapping: crm_contacts.contact_id -> warehouse_customers.customer_id.
      - source: contact_id
        target: customer_id
      # A derived field: no single source column, so `transformation` is required.
      - target: display_name
        transformation:
          kind: expression
          expression: "UPPER(full_name)"   # opaque string; evaluated downstream, not here
          inputs:
            - full_name                     # declares the field this expression reads
    join:
      type: left                            # left = crm_contacts (from), right = warehouse_customers (to)
      keys:
        - left: contact_id
          right: customer_id
```

This example is authorable-valid: it loads via `load_graph_from_yaml` and passes
`validate_field_wiring` unmodified (verified while writing this doc — not a committed test, per
the ticket's design).

## JSON form & on-disk keys

The same graph, dumped via `dump_graph_to_json` (equivalent to `dump_graph_to_yaml`, same keys):

```json
{
  "name": "crm_to_warehouse_example",
  "nodes": [
    {
      "id": "crm_contacts",
      "type": "source",
      "name": "Extract CRM Contacts",
      "config": { "endpoint": "/contacts" },
      "fields": [
        {
          "name": "contact_id",
          "type": "STRING",
          "nullable": false,
          "description": "Unique contact identifier from the CRM.",
          "metadata": {}
        },
        {
          "name": "full_name",
          "type": "STRING",
          "nullable": true,
          "description": "Contact's full name as entered in the CRM.",
          "metadata": { "sensitivity": "pii" }
        }
      ]
    },
    {
      "id": "warehouse_customers",
      "type": "target",
      "name": "Load Warehouse Customers",
      "config": {},
      "fields": [
        { "name": "customer_id", "type": "STRING", "nullable": false, "description": null, "metadata": {} },
        { "name": "display_name", "type": "STRING", "nullable": true, "description": null, "metadata": {} }
      ]
    }
  ],
  "edges": [
    {
      "from": "crm_contacts",
      "to": "warehouse_customers",
      "metadata": {},
      "mappings": [
        { "source": "contact_id", "target": "customer_id", "transformation": null, "metadata": {} },
        {
          "source": null,
          "target": "display_name",
          "transformation": {
            "kind": "expression",
            "expression": "UPPER(full_name)",
            "constant": null,
            "inputs": ["full_name"],
            "metadata": {}
          },
          "metadata": {}
        }
      ],
      "join": {
        "type": "left",
        "keys": [{ "left": "contact_id", "right": "customer_id" }],
        "metadata": {}
      }
    }
  ]
}
```

On-disk / alias keys to know, so both serializations are covered:

| Attribute | On-disk key(s) | Notes |
|---|---|---|
| `Edge.source` | `from` | Reserved word, so the Python attribute is `source`; dumps **always** emit `from` (`serialize_by_alias=True`), never `source`. |
| `Edge.target` | `to` | Same pattern as `from`; dumps always emit `to`, never `target`. |
| `Node.config` | `config` **or** `params` (load only) | Either key populates `Node.config` on load (`AliasChoices`); dumps canonically as `config` only. |
| `FieldMapping.source` / `.target` | `source` / `target` | Field-name strings; no aliasing beyond the plain keys. |
| `JoinKeyPair.left` / `.right` | `left` / `right` | Plain keys, no aliasing. |
| `Edge.join` | `join` | Omitted entirely (not `null`) when `Edge.join is None`, so join-less edges round-trip byte-identical to pre-join graphs. |
| `Node.cursor` | `cursor` | Omitted entirely (not `null`) when `Node.cursor is None`, so cursor-less nodes round-trip byte-identical to pre-DANDER-18 graphs. |

## Scope boundary

This package is **declarative only**. It does not:

- Evaluate a `Transformation`'s `expression` or interpret its `constant`.
- Generate or execute SQL for a `JoinSpec`.
- Read/write BigQuery, call any SaaS API, or move data.

Those responsibilities live in the Ingestion, Transform, and BigQuery Writer modules described in
the module map in `steering/00-project-overview.md`. The pipeline graph is the shared declarative
primitive those layers (and a future drag-drop UI) will consume — it is not itself one of the six
named modules in that table.

Related tickets: `tickets/DANDER-2-pipeline-graph-model.md` (base `Node`/`Edge`/`PipelineGraph` +
serialization), `DANDER-3` (structural validation), `DANDER-4` (node field schema), `DANDER-5`
(field mapping), `DANDER-6` (transformations), `DANDER-7` (join spec), `DANDER-8` (field-wiring
validation), `DANDER-10` (typed per-node-type config), `DANDER-11` (source request/payload spec),
`DANDER-18` (node cursor / watermark strategy).
Relevant steering: `steering/00-project-overview.md`, `steering/01-security.md`,
`steering/02-engineering.md`.

## Decision Log status

DANDER-7 shipped (`status: done`) and put join semantics **on the graph** rather than deferring them
entirely to the Transform layer — a real product decision per that ticket's "product flag." As of
this doc, `steering/00-project-overview.md`'s Decision Log does **not** yet contain an entry
recording that call; this is flagged as a gap rather than silently invented here (see
Implementation Notes in `tickets/DANDER-9-pipeline-fields-mappings-docs.md`).

DANDER-18 similarly put the watermark/cursor **strategy** on the graph node (`Node.cursor`) rather
than leaving cursor declaration entirely to the Orchestration/State layer — the same
graph-vs-downstream-layer fork as DANDER-7's join call. As of this doc,
`steering/00-project-overview.md`'s Decision Log does **not** yet contain an entry recording this
call either; flagged here rather than silently added.
