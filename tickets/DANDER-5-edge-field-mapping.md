---
id: DANDER-5
title: Field-to-field mapping on pipeline-graph connections
status: done
component: python
epic: pipeline
depends_on: [DANDER-4]
created: 2026-07-22
---

## Context

With nodes now able to declare their fields (DANDER-4), a **connection** (an `Edge`) between two
nodes needs to say **how fields flow across it**: which source-node field feeds which target-node
field. This is the field-to-field mapping at the heart of the request — the column-level lineage
that lets one data source's fields land in another node's shape (rename/project/passthrough).

This ticket adds a declarative **field-mapping** collection to the `Edge` model and preserves the
DANDER-2 YAML/JSON round-trip. It is model + serialization only. Cross-node validation — that a
mapping's source field actually exists on the edge's source node and its target field on the target
node — is DANDER-8. Custom transformation logic on a mapping is DANDER-6; this ticket covers a
straight field-to-field (direct-copy) mapping and leaves room for that extension.

Mappings reference fields **by name** (the identifiers from DANDER-4), never by value; no data or
secrets belong in a mapping (`steering/01-security.md`).

## Acceptance Criteria

- [ ] A Pydantic v2 `FieldMapping` model with at least: a source-field reference and a target-field
      reference (both field-name strings), plus an optional free-form `metadata` dict via a default
      factory. Fully type-annotated with Google-style docstrings.
- [ ] `Edge` gains an ordered `mappings` collection of `FieldMapping`, defaulting to empty via a
      proper default factory (no mutable default args). An edge with no mappings loads and dumps
      exactly as before (backward compatible with DANDER-2/DANDER-4 graphs).
- [ ] The naming of a mapping's source/target field keys is consistent with the rest of the model
      and documented; the on-disk keys are stable and covered by tests.
- [ ] Mappings round-trip stably through **both** YAML and JSON via the existing load/dump
      functions: load → dump → load yields an equivalent graph (model equality), including edges
      that carry mappings with `metadata`.
- [ ] Google-style docstrings on new/changed public models; fully type-annotated per
      `steering/languages/python.md`. No secrets or field values anywhere.
- [ ] pytest tests cover: an edge loads its mappings from YAML and from JSON; multiple mappings on
      one edge preserve order; mappings round-trip stably in both formats; and a mapping-less edge
      is unchanged. Tests live under `tests/` and require no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the mapping model + serialization and its tests (no
      transformation logic — DANDER-6; no cross-node field-existence validation — DANDER-8).

## Design

### Approach

This is a pure model + serialization change inside `src/dander/pipeline/graph.py`, mirroring the
shape DANDER-4 uses for `NodeField` on `Node`. We add one new Pydantic v2 model, `FieldMapping`,
and give `Edge` an ordered `mappings: list[FieldMapping]` collection defaulting to empty via a
default factory. No new module, no new dependency, no changes to the four load/dump functions —
they already recurse through nested Pydantic models, so an `Edge` that carries `mappings`
round-trips through both YAML and JSON with zero changes to the serialization layer. An edge with
no mappings dumps exactly as before because an empty list serializes to `[]`/`mappings: []` and,
more importantly, model equality is preserved on the load→dump→load cycle (the existing
round-trip tests already prove the mechanism; we extend the fixtures to exercise mappings).

A `FieldMapping` is column-level lineage: it names a **source-node field** and a **target-node
field**, both by their field-name string (the `name` identifiers declared on nodes in DANDER-4).
It carries only names and an optional free-form `metadata` dict — never a value, never sample
data, never a secret (`steering/01-security.md`). This ticket implements the direct-copy
(passthrough/rename/project) case only; custom transformation logic is DANDER-6 and cross-node
field-existence validation is DANDER-8. To leave a clean seam for DANDER-6, the model is a plain
value object whose meaning today is "copy source field to target field"; DANDER-6 can add an
optional transform descriptor without changing these two keys or breaking round-trip.

### On-disk key naming (decision — see "Trade-offs")

`FieldMapping` exposes Python attributes **`source`** and **`target`** with **on-disk keys
`source`/`target`** (no aliases). Rationale:

- It reuses the model's existing directional vocabulary: `Edge` already calls its endpoints
  `source`/`target` in Python, so a mapping reading "this source field → this target field" is
  consistent with the rest of the model (acceptance criterion 3).
- Unlike `Edge`'s node-id keys — which use the `from`/`to` aliases only because `from` is a Python
  reserved word — `source`/`target` are legal identifiers, so **no alias is needed**; the on-disk
  key equals the attribute name. That keeps this model simpler than `Edge` while staying readable
  on disk.
- We deliberately do **not** reuse the `from`/`to` on-disk keys here: those read at the graph as
  "from node n1 to node n2", and reusing them at field level would blur node-lineage and
  field-lineage in the serialized document.

The keys `source`/`target` are the stable on-disk contract and are asserted directly in tests
(criterion 3).

### Interfaces / classes

- **`FieldMapping(BaseModel)`** — new. A single field-to-field (direct-copy) lineage mapping on an
  edge.
  - `source: str` — the source-node field name this mapping reads from.
  - `target: str` — the target-node field name this mapping writes to.
  - `metadata: dict[str, Any] = Field(default_factory=dict)` — optional free-form tags/labels
    (e.g. a mapping note, a lineage tag). Docstring states it holds labels only, never values or
    secrets, mirroring the DANDER-4 `metadata` convention.
  - `model_config = ConfigDict(populate_by_name=True)` for consistency with the other models
    (harmless here since attribute names equal on-disk keys; keeps the family uniform).
  - Fully type-annotated with a Google-style class docstring documenting the `source`/`target`
    semantics and the "names only, never values" invariant.

- **`Edge(BaseModel)`** — changed. Add one field, ordered and after the existing ones:
  - `mappings: list[FieldMapping] = Field(default_factory=list)` — column-level lineage across
    this connection; empty by default. List preserves declaration order (criterion: multiple
    mappings preserve order). Update the `Edge` docstring's Attributes section to document
    `mappings`. No change to `Edge`'s existing `source`/`target`/`metadata` fields or its
    `from`/`to` aliasing.

`FieldMapping` must be defined **before** `Edge` in the module (or use a forward reference under
`from __future__ import annotations`, which the module already imports) so the annotation resolves.

### Files to touch

- `src/dander/pipeline/graph.py` — add `FieldMapping`; add `mappings` to `Edge`; extend the `Edge`
  docstring. No changes to `Node`, `PipelineGraph`, or the load/dump functions.
- `tests/pipeline/test_graph.py` — extend fixtures/tests (see Test seams). Prefer adding to the
  existing YAML/JSON docs and a small number of focused new tests over a new test module, matching
  the current file's structure.

No changes to `__init__.py` exports are required unless DANDER-4/existing code re-exports model
classes there (it does not today); if a later ticket adds re-exports, `FieldMapping` should join
them, but that is out of scope here.

### Trade-offs

- **`source`/`target` keys vs. `from`/`to` vs. `src_field`/`dst_field`.** Chose `source`/`target`
  for consistency with `Edge`'s Python vocabulary and because they need no alias. Rejected
  `from`/`to` (reserved-word alias machinery for no benefit, and collides conceptually with
  node-level edges). Rejected `src_field`/`target_field`-style names as more verbose without being
  clearer, given the enclosing `FieldMapping` type already scopes them to fields. This is the one
  genuinely open naming choice in the ticket; it is now decided and pinned by tests.
- **List vs. dict for `mappings`.** A `dict[target_field, source_field]` would enforce
  single-writer-per-target for free, but the ticket requires an **ordered** collection and leaves
  room for DANDER-6 transforms (which want a full object per mapping, not a bare string), and a
  dict cannot carry per-mapping `metadata`. A `list[FieldMapping]` is the right shape; any
  uniqueness/one-writer rules belong to validation (DANDER-8), not this model.
- **Extend `Edge` vs. new wrapper type.** Adding `mappings` directly to `Edge` keeps the on-disk
  document flat and backward compatible; a separate mapping-container type would add nesting for no
  gain at this stage.
- **No custom serializers.** Relying on Pydantic's recursive dump keeps the load/dump functions
  untouched and the round-trip guarantee inherited rather than re-implemented.

### Test seams

All unit tests, no network, under `tests/pipeline/test_graph.py`:

- **Load from YAML** and **from JSON**: an edge with two `mappings` (each with `source`/`target`,
  one also carrying `metadata`) parses into `FieldMapping` instances with the expected values.
- **Order preserved**: assert `[m.source for m in edge.mappings]` (and targets) match declaration
  order for a multi-mapping edge.
- **On-disk keys stable**: dump an `Edge` with a mapping and assert the serialized text contains
  `source`/`target` mapping keys (and, per the existing style, that the edge itself still emits
  `from`/`to`); assert no unexpected key names leak.
- **Round-trip stable, both formats**: extend the existing `test_yaml_round_trip_is_stable` /
  `test_json_round_trip_is_stable` fixtures (`_YAML_DOC` / `_JSON_DOC`) so at least one edge
  carries mappings-with-metadata, and assert load→dump→load model equality (this reuses the
  existing proven pattern).
- **Backward compatibility**: a mapping-less edge still yields `edge.mappings == []` and its dump
  is unchanged from the DANDER-2/DANDER-4 shape (extend `_assert_expected_graph` or add a focused
  assertion).
- **Independent default containers**: like the existing `Node`/`Edge` default-container test,
  assert two `FieldMapping` instances get fresh, independent `metadata` dicts (no mutable default
  args).

Nothing is mocked — the models and file I/O to `tmp_path` are exercised directly, consistent with
the existing test file.

### Notes / flags

- Depends on **DANDER-4**, which introduces the per-node field schema and the `metadata`-dict
  convention this model mirrors. DANDER-4 is not yet merged at design time; the Code agent should
  build on the merged DANDER-4 `Edge`/`Node` shape and follow whatever exact `metadata` convention
  DANDER-4 lands (naming, default factory). If DANDER-4's `metadata` key or default-factory pattern
  differs from what is assumed here, match DANDER-4 for consistency and note the deviation.
- Explicitly **out of scope** (do not implement): transform logic on a mapping (DANDER-6),
  join specs (DANDER-7), and any check that a mapping's `source`/`target` names exist on the
  connected nodes (DANDER-8). The model must leave room for the DANDER-6 transform extension but
  add nothing for it now.
- Keep `uv run ruff check`, `uv run mypy`, `uv run pytest` green.

## Implementation Notes

Implemented exactly per Design, no deviations.

- **`src/dander/pipeline/graph.py`**: added `FieldMapping(BaseModel)` (defined immediately before
  `Edge`), with `source: str`, `target: str` (no aliases — on-disk keys equal attribute names),
  and `metadata: dict[str, Any] = Field(default_factory=dict)`. `model_config =
  ConfigDict(populate_by_name=True)` for consistency with the other models. Google-style
  docstring documents the `source`/`target` semantics and the "names/labels only, never values or
  secrets" invariant, referencing DANDER-6 (transform) and DANDER-8 (validation) as the deferred
  seams.
  `Edge` gained `mappings: list[FieldMapping] = Field(default_factory=list)` as its last field
  (after `metadata`), with the `Edge` docstring's Attributes section updated. No changes to
  `Edge`'s existing `source`/`target`/`metadata` fields, its `from`/`to` aliasing, `Node`,
  `PipelineGraph`, or any of the four load/dump functions — the existing recursive
  Pydantic dump/parse already carries `mappings` through YAML and JSON with zero serialization
  changes, confirmed by the round-trip tests below.

- **`tests/pipeline/test_graph.py`**: extended per the ticket's Test seams, favoring additions to
  the existing file/fixtures over a new module:
  - `_YAML_DOC` / `_JSON_DOC` now include an edge with two `mappings` (one carrying `metadata`,
    one without), so the existing `test_load_multi_node_edge_graph_from_yaml/json`,
    `test_yaml_round_trip_is_stable`, and `test_json_round_trip_is_stable` tests now exercise
    mappings-with-metadata end-to-end (load, and load→dump→load model equality) without any new
    test functions needed for those paths.
  - `_assert_expected_graph` extended to assert mapping count, per-mapping `source`/`target`
    values in declaration order, and per-mapping `metadata` (including the empty-metadata case).
  - Added `test_field_mapping_on_disk_keys_are_source_and_target` — validates/dumps a
    `FieldMapping` directly and pins the on-disk `source`/`target`/`metadata` keys (criterion 3).
  - Added `test_edge_mappings_preserve_declaration_order` — asserts mapping order survives both
    YAML and JSON loads for a multi-mapping edge.
  - Added `test_dump_emits_stable_source_target_mapping_keys` — dumps an edge with one mapping to
    both YAML and JSON and asserts the serialized text contains the mapping's `source`/`target`
    keys while the edge itself still emits `from`/`to` (not `source`/`target`) at the edge level.
  - Added `test_edge_with_no_mappings_is_unchanged_from_prior_shape` — a mapping-less `Edge`
    yields `mappings == []` and its full dump matches the pre-DANDER-5 shape plus an empty
    `mappings: []` (backward compatibility).
  - Extended `test_node_and_edge_defaults_are_independent_empty_containers` with two
    `FieldMapping` instances to assert their default `metadata` dicts are fresh/independent (no
    mutable default args).
  - Updated `test_edge_dump_emits_reserved_keyword_keys_not_attribute_names` to include the new
    `mappings: []` key in its exact-dict assertion (it dumps a mapping-less edge, so this doubles
    as another backward-compatibility check).

- **Toolchain**: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, and
  `uv run pytest` all pass on the touched files (48 tests total, all green). Note:
  `uv run ruff check` on the *whole repo* flags one pre-existing `E501` in
  `scripts/watch_workflows.py`, which was already modified in the working tree before this ticket
  started (per `git status` at task start) and is unrelated to this change — left untouched as
  out of scope.

- **Deviation check**: DANDER-4's `NodeField`/`Node.fields` shape (as merged) matches what the
  Design assumed — `metadata: dict[str, Any] = Field(default_factory=dict)` with the same
  labels-only convention — so `FieldMapping.metadata` mirrors it exactly with no deviation needed.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-22 — PASS

Reviewed `src/dander/pipeline/graph.py` and `tests/pipeline/test_graph.py` against all eight
acceptance criteria, the steering files, and `steering/languages/python.md`.

**Acceptance criteria — all met:**
1. `FieldMapping(BaseModel)` (Pydantic v2) with `source: str`, `target: str`, and
   `metadata: dict[str, Any] = Field(default_factory=dict)`. Fully type-annotated, Google-style
   class docstring documenting the source→target semantics and the "names/labels only, never
   values or secrets" invariant.
2. `Edge` gains `mappings: list[FieldMapping] = Field(default_factory=list)` as its last field
   (ordered, no mutable default). Old graphs without a `mappings` key still load (defaults fill
   in); the empty-list → `mappings: []` dump follows the same established convention DANDER-4 set
   for `Node.fields` and Edge's `metadata: {}`, and round-trip model equality holds.
3. On-disk keys `source`/`target` (no aliases) — consistent with `Edge`'s Python vocabulary,
   documented in the docstring/Design, and pinned by
   `test_field_mapping_on_disk_keys_are_source_and_target` +
   `test_dump_emits_stable_source_target_mapping_keys` (which also confirms the edge itself still
   emits `from`/`to`, not `source`/`target`, at the edge level).
4. Stable round-trip in both formats: `_YAML_DOC`/`_JSON_DOC` now carry an edge with two mappings
   (one with `metadata`), exercised by `test_yaml_round_trip_is_stable` /
   `test_json_round_trip_is_stable` (load→dump→load model equality).
5. Docstrings updated on `FieldMapping` (new) and `Edge` (Attributes section adds `mappings`);
   fully type-annotated; no secrets or field values anywhere in the diff.
6. Test coverage: load-from-YAML and load-from-JSON, multi-mapping order preservation, both-format
   round-trip, and mapping-less-edge backward compatibility, plus an independent-default-container
   test extended to `FieldMapping`. All under `tests/`, no network.
7. `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` all green on
   the touched files; full suite is 46 tests green and full `mypy src` clean. The one repo-wide
   `ruff` E501 is in `scripts/watch_workflows.py` — outside this ticket's diff (only `graph.py`
   and `test_graph.py` changed) and accurately disclosed in Implementation Notes; not attributable
   to DANDER-5.
8. No steering violations. Scope held to model + serialization + tests — no transform logic
   (DANDER-6) and no cross-node field-existence validation (DANDER-8).

**Security:** grep of the diff for credential-shaped literals is clean; no new secrets, so
`.env.example` correctly unchanged; mappings reference fields by name only.

No blocking issues. Verdict: **PASS** → status `done`.
