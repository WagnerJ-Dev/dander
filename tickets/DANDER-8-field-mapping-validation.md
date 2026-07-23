---
id: DANDER-8
title: Validate field mappings, transformations, and joins against node schemas
status: done
component: python
epic: pipeline
depends_on: [DANDER-4, DANDER-5, DANDER-6, DANDER-7]
created: 2026-07-22
---

## Context

DANDER-4–7 add declarative fields, mappings, transformations, and joins to the graph, but a graph
can still be *shaped* correctly yet *semantically* wrong: a mapping that references a field no node
declares, a transformation whose input field doesn't exist, a join key that isn't on the joined
node, or two fields on one node sharing a name. Just as DANDER-3 makes an invalid **structure** fail
loud and actionable, this ticket makes an invalid **field wiring** fail loud and actionable —
extending the same validation surface (`dander.pipeline.graph_ops` / typed errors) rather than
inventing a parallel one.

This is Python-only and pure (no I/O, no network). It depends on all four model tickets because it
validates their references against node field schemas. Error messages name the offending element
(the field name, the edge, the node) and, per `steering/01-security.md`, carry graph **structure
only** — field names and ids — never field `metadata`/values, transformation payloads, or node
`config`.

## Acceptance Criteria

- [ ] New typed errors under the existing `GraphValidationError` hierarchy for field-wiring
      failures, each naming the offending element(s): at minimum a duplicate-field-name-within-a-node
      error, an unknown-field-reference error (used by mappings, transformations, and joins), and a
      join-specific error where appropriate. Reuse the existing hierarchy/module so callers can still
      catch `GraphValidationError` generically.
- [ ] Validation checks, integrated with the DANDER-3 `validate` entrypoint (or a clearly documented
      companion that composes with it) and ordered so structural checks (DANDER-3) run first:
      - field names are unique within each node;
      - every `FieldMapping`'s source field exists on the edge's **source** node and its target
        field exists on the edge's **target** node;
      - every transformation's declared input field references resolve to fields on the appropriate
        node (no expression evaluation — reference resolution only);
      - every join key pair references a field that exists on the correct (left/right) joined node.
- [ ] A well-wired graph passes validation with no error raised; each failure mode raises the
      **correct** typed error with a message that names the offending field/edge/node.
- [ ] The contract for when field-wiring validation runs relative to structural validation is
      documented and tested (e.g. structural errors surface before field-wiring errors on a graph
      with both).
- [ ] Google-style docstrings on the new errors and validation functions; fully type-annotated per
      `steering/languages/python.md`. Error messages contain structure only — never field values,
      `metadata`, transformation payloads, or node `config`.
- [ ] pytest tests cover: a fully-wired valid graph validates cleanly; and each failure mode
      (duplicate field name, mapping to a missing source field, mapping to a missing target field,
      transformation input referencing a missing field, join key missing on a joined node) raises
      the correct typed error naming the offending element. Tests live under `tests/` and require no
      network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond field-wiring validation + its errors and tests (no
      execution, no SQL generation, no changes to the stored format).

## Design

### Approach

DANDER-3 already established the validation surface: a typed `GraphValidationError` hierarchy in
`dander.pipeline.errors`, and a set of small, pure `_check_*` functions in
`dander.pipeline.graph_ops` composed by a single `validate(graph)` entrypoint that runs them in a
fixed, dependency-ordered sequence. This ticket **extends that same surface** rather than inventing
a parallel one: new error subclasses on the existing hierarchy, and new `_check_*` functions in the
same module.

Field-wiring validation is only meaningful once the graph is *structurally* sound — node ids are
unique and every edge endpoint resolves to a real node — because the checks index fields by node id
and walk edges to reach the source/target node's field set. So we compose rather than merge: keep
`validate(graph)` as the pure **structural** gate (unchanged; still called by `topological_order`
and existing callers — SRP + backward compatibility), and add a companion
`validate_field_wiring(graph)` that **first calls `validate(graph)`** (structural) and only then
runs the field-wiring checks. This guarantees the documented/tested contract: on a graph that has
*both* a structural fault and a field-wiring fault, the structural error surfaces first. Callers who
want the full gate call `validate_field_wiring`; callers who only need structure keep calling
`validate`.

All checks are pure, side-effect-free functions of the `PipelineGraph` — no I/O, no network, nothing
persisted onto the model — matching the rest of `graph_ops`. No expression is parsed or evaluated:
transformations are checked by **reference resolution only** (do the named input fields exist), per
DANDER-6's boundary.

**Security (`steering/01-security.md`): error messages carry graph structure only** — field names,
node ids, and edge endpoint ids. They must **never** include a node's `config`, a field's or edge's
`metadata`, a field value, a transformation's expression/constant payload, or a join's metadata. In
particular the transformation check names the *missing input field* and its node, never the
expression string it came from.

### New errors (`dander/pipeline/errors.py`)

All subclass the existing `GraphValidationError`, so `except GraphValidationError` still catches
every failure and existing structural handlers are unaffected.

- **`DuplicateFieldNameError(GraphValidationError)`** — two fields on one node share a `name`.
  Attributes: `node_id: str`, `field_name: str`. Message names both (e.g.
  `Duplicate field name 'email' on node 'sf_contacts'.`).

- **`UnknownFieldReferenceError(GraphValidationError)`** — the generic "a reference points at a
  field the relevant node does not declare," used by mappings, transformations, and joins.
  Attributes: `node_id: str` (the node that should declare it), `field_name: str` (the missing
  field), `edge: tuple[str, str]` (the offending edge as `(source_id, target_id)`), and
  `reference_kind: FieldReferenceKind`. A small `FieldReferenceKind(StrEnum)` discriminates the
  reference site — `MAPPING_SOURCE`, `MAPPING_TARGET`, `TRANSFORMATION_INPUT`, `JOIN_LEFT`,
  `JOIN_RIGHT` — so one error type serves all sites while the message and attribute stay precise
  (e.g. `Mapping on edge 'sf_contacts' -> 'stg_contacts' references field 'emial' not declared on
  source node 'sf_contacts'.`).

- **`JoinKeyFieldError(UnknownFieldReferenceError)`** — the "join-specific error where appropriate."
  A subclass (not a sibling), so join failures are still caught by handlers targeting
  `UnknownFieldReferenceError` or `GraphValidationError`, while a caller that cares specifically
  about join wiring can catch this. Raised for `JOIN_LEFT`/`JOIN_RIGHT` reference kinds; may add a
  `key_index: int` attribute to name which key pair in the join failed.

### New validation (`dander/pipeline/graph_ops.py`)

A tiny derived index mirroring the existing `AdjacencyIndex` pattern:

- **`_FieldIndex`** (`@dataclass(frozen=True)`) — `node_id -> frozenset[str]` of declared field
  names, with a `has(node_id, field_name) -> bool` helper and a `from_graph` classmethod. Built
  **after** the duplicate-name check (so a node with duplicate names is already rejected and the
  set is unambiguous). Assumes ids are unique (guaranteed because `validate_field_wiring` runs
  structural `validate` first).

Pure check functions, each raising the correct typed error:

- `_check_duplicate_field_names(graph)` → `DuplicateFieldNameError`. Per node, track seen field
  names; first repeat raises.
- `_check_mapping_fields(graph, index)` → `UnknownFieldReferenceError`. Per edge, per `FieldMapping`:
  source-field ref must be `index.has(edge.source, …)` (kind `MAPPING_SOURCE`); target-field ref
  must be `index.has(edge.target, …)` (kind `MAPPING_TARGET`).
- `_check_transformation_fields(graph, index)` → `UnknownFieldReferenceError` (kind
  `TRANSFORMATION_INPUT`). For each transformation's declared **input field references** (zero or
  more source field names, per DANDER-6), each must exist on the edge's **source** node. Zero inputs
  (e.g. `constant`/derived) → nothing to check. Reference resolution only; the expression payload is
  never inspected or included in any message.
- `_check_join_fields(graph, index)` → `JoinKeyFieldError`. For each edge that carries a join spec,
  each key pair: the left field must exist on the edge's **source** (`from`) node (kind `JOIN_LEFT`),
  the right field on the **target** (`to`) node (kind `JOIN_RIGHT`), consistent with DANDER-7's
  left↔from / right↔to convention.

Composite entrypoint:

```python
def validate_field_wiring(graph: PipelineGraph) -> None:
    validate(graph)                       # DANDER-3 structural gate — surfaces first
    _check_duplicate_field_names(graph)   # must precede index build
    index = _FieldIndex.from_graph(graph)
    _check_mapping_fields(graph, index)
    _check_transformation_fields(graph, index)
    _check_join_fields(graph, index)
```

Docstring states the ordering contract explicitly (structural first, then duplicate-name, then the
three reference checks) and lists every error it may raise.

### Files to touch

- `src/dander/pipeline/errors.py` — add `FieldReferenceKind`, `DuplicateFieldNameError`,
  `UnknownFieldReferenceError`, `JoinKeyFieldError`; extend the module docstring to note the new
  field-wiring failure modes still carry structure only.
- `src/dander/pipeline/graph_ops.py` — add `_FieldIndex`, the four `_check_*` functions, and
  `validate_field_wiring`.
- `tests/pipeline/test_field_validation.py` (new) — field-wiring tests, kept separate from the
  structural `test_graph_ops.py`. Small in-memory graphs via helpers like the existing `_node`/
  `_edge`; no network, no mocks needed (pure functions).

### Trade-offs

- **Compose vs. merge into `validate`.** Composing (`validate_field_wiring` calls `validate` then
  the field checks) keeps `validate` a pure structural gate for existing callers (`topological_order`)
  and makes the "structural-first" contract trivially true and testable. The cost is two public
  entrypoints; documented clearly, this is the ISP-friendly shape.
- **One generic `UnknownFieldReferenceError` (+ join subclass) vs. one error per site.** A single
  error with a `reference_kind` discriminator keeps the hierarchy small and lets callers catch all
  field-reference failures at once, while `reference_kind`/the message stay precise. The ticket
  explicitly asks for a reused unknown-reference error plus a join-specific one — this matches.
- **`_FieldIndex` helper vs. inline dict.** A small frozen index mirrors `AdjacencyIndex`, reads
  cleanly, and centralizes the "does node N declare field F" lookup used by three checks.
- **Duplicate-name check before index build.** A set-based index would silently swallow duplicates;
  running the duplicate check first keeps the index honest and yields the correct, specific error.

### Test seams

Pure functions over hand-built `PipelineGraph` objects — nothing to mock, no network. Cover:
(1) a fully-wired valid graph passes `validate_field_wiring` with no raise; each failure mode raises
the correct typed error and its naming attributes are asserted: (2) duplicate field name on a node;
(3) mapping to a missing **source** field; (4) mapping to a missing **target** field; (5)
transformation input referencing a missing field; (6) join key missing on a joined node
(`JoinKeyFieldError`, and assert it is also caught as `UnknownFieldReferenceError`); (7) **ordering** —
a graph with both a structural fault (e.g. duplicate node id / dangling edge) and a field-wiring
fault raises the *structural* error first. Assert messages/attributes name the offending element and
that no message leaks `metadata`/`config`/payload/values.

### Notes / flags for the Code agent

- **Dependency alignment (primary risk).** DANDER-4–7 are not yet implemented; their exact attribute
  names are set by *their* designs. This design assumes: `Node.fields` (ordered) of a field spec with
  a `.name`; `Edge.mappings` of `FieldMapping` exposing a source-field-name and target-field-name
  attr; a transformation exposing its **input field references** as a list of source field-name
  strings; and an optional `Edge` join spec exposing an ordered collection of left/right field-name
  key pairs. **Match the real names once DANDER-4–7 land** — the check logic is unaffected, only the
  attribute access changes. If a name differs, adjust the `_check_*` accessors, not the structure.
- If a transformation can also be attached at the **edge/mapping level for a derived field with no
  single source** (DANDER-6), iterate those the same way — resolve each declared input field name
  against the source node; a zero-input transformation is a no-op for this check.
- Keep new tests green under `uv run ruff check`, `uv run mypy`, `uv run pytest`.

## Implementation Notes

Implemented exactly per Design, extending the existing DANDER-3 validation surface rather than
inventing a parallel one. DANDER-4–7 had already landed by the time this ticket was picked up, so
the "notes/flags for the Code agent" dependency-alignment risk was resolved by reading the real
models directly (`Node.fields: list[NodeField]` with `.name`; `Edge.mappings: list[FieldMapping]`
with `.source`/`.target`; `FieldMapping.transformation: Transformation | None` with
`.inputs: list[str]`; `Edge.join: JoinSpec | None` with `.keys: list[JoinKeyPair]` and
`.left`/`.right`) — no attribute-name deviations were needed; the design's assumed shapes matched
exactly.

- **`src/dander/pipeline/errors.py`** — added, all subclassing `GraphValidationError`:
  - `DuplicateFieldNameError` (`node_id`, `field_name`).
  - `FieldReferenceKind` (`StrEnum`): `MAPPING_SOURCE`, `MAPPING_TARGET`,
    `TRANSFORMATION_INPUT`, `JOIN_LEFT`, `JOIN_RIGHT`.
  - `UnknownFieldReferenceError` (`node_id`, `field_name`, `edge: tuple[str, str]`,
    `reference_kind`) — one reusable error for every reference site, message built from two small
    private lookup dicts (`_REFERENCE_KIND_DESCRIPTIONS`, `_REFERENCE_KIND_SIDE`) keyed by
    `reference_kind` so the message names the right description ("Mapping"/"Transformation
    input"/"Join key") and the right side ("source"/"target") without a long if/elif chain.
  - `JoinKeyFieldError(UnknownFieldReferenceError)` — adds `key_index: int`, raised only for
    `JOIN_LEFT`/`JOIN_RIGHT`.
  - Module docstring extended to describe the field-wiring failure modes and restate the
    structure-only invariant (now explicitly: never `config`, `metadata`, a field value, or a
    transformation payload).
- **`src/dander/pipeline/graph_ops.py`** — added:
  - `_FieldIndex` (`@dataclass(frozen=True)`), mirroring `AdjacencyIndex`: `from_graph` classmethod
    plus a `has(node_id, field_name) -> bool` helper.
  - `_check_duplicate_field_names`, `_check_mapping_fields`, `_check_transformation_fields`,
    `_check_join_fields` — pure functions exactly as designed.
  - `validate_field_wiring(graph)` — composite entrypoint: calls structural `validate(graph)`
    first, then duplicate-name check, then builds `_FieldIndex`, then the three reference checks,
    in the fixed order the Design specifies. `validate` itself is untouched (still the pure
    structural gate used by `topological_order`).
  - Module docstring extended to document the composition contract (structural-first) and the
    security invariant.
- **`src/dander/pipeline/__init__.py`** — exported the new public symbols (`validate_field_wiring`,
  `DuplicateFieldNameError`, `FieldReferenceKind`, `UnknownFieldReferenceError`,
  `JoinKeyFieldError`) alongside the existing DANDER-3 exports.
- **`tests/pipeline/test_field_validation.py`** (new, 11 tests) — a fully-wired valid graph
  (mapping + expression-transformation + join) passes with no raise; duplicate field name; mapping
  missing source field; mapping missing target field; transformation input referencing a missing
  field; a zero-input (`constant`) transformation is a no-op even when the source node declares no
  fields; join key missing on the left (source) node and on the right (target) node, each asserting
  `JoinKeyFieldError` is also catchable as `UnknownFieldReferenceError`; a second join key pair's
  failure reports the correct `key_index` (not the first); the documented ordering contract
  (duplicate node id + a field-wiring fault on the same graph raises the structural
  `DuplicateNodeIdError`, not a field-wiring error); and a dedicated leak-check asserting that a
  message never contains node `config`, mapping `metadata`, or a transformation's `expression`
  payload even when the fixture deliberately embeds secret-shaped/sensitive-looking strings there.

No deviations from the Design. Scope stayed within field-wiring validation + its errors and tests —
no execution, no SQL generation, no changes to the stored graph format.

Toolchain: `uv run ruff check`, `uv run ruff format --check`, and `uv run mypy` are clean on every
file touched; `uv run pytest` — full suite (92 tests, including the 11 new ones) passes. Note: a
repo-wide `uv run ruff check .` / `ruff format --check .` surfaces one pre-existing line-length
issue in `scripts/watch_workflows.py` — that file was already modified outside this ticket
(unrelated to `dander.pipeline`) and is out of DANDER-8's scope, so it was left untouched.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-22 — PR-Review — PASS

All acceptance criteria met, no blocking issues.

- **Typed errors (AC1):** `DuplicateFieldNameError`, `UnknownFieldReferenceError`, and
  `JoinKeyFieldError` added in `errors.py`, all subclassing `GraphValidationError`
  (`JoinKeyFieldError` further subclasses `UnknownFieldReferenceError`), so `except
  GraphValidationError` still catches every failure. `FieldReferenceKind(StrEnum)` discriminates
  the five reference sites; each error names its offending element via attributes and message.
- **Checks + composition (AC2):** `validate_field_wiring` composes structural `validate` first,
  then `_check_duplicate_field_names`, then builds `_FieldIndex`, then mapping / transformation /
  join checks in the fixed order. `validate` is untouched (still the pure structural gate for
  `topological_order`). Mapping source→source node, target→target node; transformation inputs→
  source node; join left→source, right→target — all correct and consistent with the DANDER-6/7
  conventions. `source is None` (derived-field) mappings correctly skip the source check.
- **Ordering contract (AC4):** documented in the `validate_field_wiring` docstring and module
  docstrings, and tested (`test_structural_error_surfaces_before_field_wiring_error`).
- **Docstrings/typing/security (AC5):** Google-style docstrings on every new error and function;
  fully type-annotated (mypy clean). Messages carry structure only — a dedicated leak test asserts
  node `config`, mapping `metadata`, and the transformation `expression` payload never appear in
  any message, even with secret-shaped fixture values.
- **Tests (AC6):** `tests/pipeline/test_field_validation.py` — 11 pure, network-free tests covering
  the valid graph, all five failure modes, zero-input no-op, second-key-pair `key_index`,
  `JoinKeyFieldError` catchable as `UnknownFieldReferenceError`, the ordering contract, and the
  leak check.
- **Toolchain (AC7):** on the DANDER-8 files, `uv run ruff check`, `uv run ruff format --check`,
  and `uv run mypy` are clean; full `uv run pytest` suite (92 tests) passes.
- **Scope/security (AC3, AC8):** diff confined to `errors.py`, `graph_ops.py`, `__init__.py`, and
  the new test file — no execution, SQL generation, or stored-format change. No hardcoded secrets;
  the only Secret Manager string is an indirect resource-name reference inside a leak-assertion
  test, which steering permits. The pre-existing `scripts/watch_workflows.py` lint issue is outside
  this ticket's scope, as the Implementation Notes state.
