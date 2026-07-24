---
id: DANDER-17
title: Field-level casting overrides and generic data-quality tests on NodeField
status: done
component: python
epic: pipeline-config
depends_on: []
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (see DANDER-10 for the shared
review context).

`steering/00-project-overview.md` promises "inferred type casting to BigQuery types with per-field
overrides" and dbt-style generic tests (not-null / unique / accepted-values / relationships). But
`NodeField` in `src/dander/pipeline/graph.py` (delivered by DANDER-4) today has neither a raw-vs-
target-type distinction nor a `tests` list — a single free-form `type` and no data-quality assertion
capability.

This ticket extends `NodeField` with: (1) a raw-vs-target-type distinction so a per-field **casting
override** can be declared, and (2) a `tests` list of declarative **generic data-quality tests**
(not-null / unique / accepted-values / relationships), each with its parameters. Model +
serialization + validation only — no casting is applied and no test is executed here (that is the
Transform/Writer layer, per the overview).

## Acceptance Criteria

- [ ] `NodeField` gains a raw-vs-target-type distinction enabling a **per-field casting override**
      (e.g. a declared raw/source type plus a target/cast type), backward compatible with the current
      single `type` (a field declaring only the existing `type` still loads).
- [ ] `NodeField` gains a `tests` collection of declarative generic tests covering at least:
      not-null, unique, accepted-values (with its value list), and relationships (referencing another
      node/field). Each test is a typed model with the params that kind needs; kinds are a named
      closed set. Fully type-annotated.
- [ ] Boundary constraints are enforced (e.g. accepted-values requires a non-empty value list; a
      relationships test requires its referenced field), raising a clear validation error. No test is
      executed and no casting is applied here. Whether referenced fields resolve cross-node is out of
      scope (that is the DANDER-8 style validation lineage; note it, don't implement it).
- [ ] Backward compatibility: a `NodeField` with no casting override and no tests loads and
      round-trips exactly as a DANDER-4 field did.
- [ ] Casting overrides and tests round-trip stably through YAML and JSON via the existing load/dump
      functions (load → dump → load model equality).
- [ ] Google-style docstrings noting tests/casts are declarative and executed downstream; typed per
      `steering/languages/python.md`. No secrets or real sample values in fixtures (accepted-values
      lists use synthetic tokens).
- [ ] pytest tests cover: a field loads a casting override and each test kind from YAML and JSON;
      boundary constraints reject malformed tests; round-trip stability; and a plain DANDER-4 field is
      unchanged. Tests live under `tests/`, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the `NodeField` extension + validation + serialization
      + tests. No casting execution, no test execution, no cross-node resolution.

## Design

### Approach

This is a pure model extension to `src/dander/pipeline/graph.py`, in the same declarative-and-inert
spirit as the existing `Transformation`/`JoinSpec` work: we add *shape* and *boundary validation*
only — no casting is applied and no test is executed here (that is the Transform/Writer layer, per
`steering/00-project-overview.md`). We deliberately reuse the two patterns this module already
established rather than invent new ones: a `StrEnum` for a closed, importable kind set (like
`TransformationKind`/`JoinType`), and a single Pydantic model carrying all per-kind params guarded
by one `@model_validator(mode="after")` (exactly like `Transformation._check_kind_payload`). Reusing
those keeps the module internally consistent and the downstream branch surface uniform.

**Casting override — additive, not a rename.** `NodeField.type` stays as the field's declared
raw/source type (its current meaning, unchanged), and we add an optional `cast_to: str | None =
None` for the target/cast BigQuery type. The raw-vs-target distinction is therefore: `type` = raw,
`cast_to` = target override. `cast_to is None` means "no override — use `type` as-is." This is the
maximally backward-compatible framing: a DANDER-4 field that declares only `type` loads unchanged
and `cast_to` defaults to `None`. (Trade-off below covers the rejected rename-with-alias option.)

**Tests — closed-set discriminated model.** Add a `TestKind(StrEnum)` with `NOT_NULL`, `UNIQUE`,
`ACCEPTED_VALUES`, `RELATIONSHIPS`, and a single `FieldTest(BaseModel)` holding the discriminator
plus each kind's optional params, validated by one after-validator that enforces the per-kind
required/forbidden params. `NodeField` gains `tests: list[FieldTest] = Field(default_factory=list)`.

**Serialization needs no change.** The new attributes ride the existing `model_dump(by_alias=True,
mode="json")` path. Emitting `tests: []` and `cast_to: null` on a plain field is consistent with how
the module already dumps empty-list defaults (`Node.fields`, `Edge.mappings` → `[]`) and `None`
defaults (`FieldMapping.source`/`transformation`/`description` → `null`). `_dump_graph_payload` only
special-cases join-less `join`; the new fields need no analogous stripping. Round-trip is
load → dump → load **model equality** (AC5), which holds for empty-list/`None` defaults — so
`load_graph_from_*`/`dump_graph_to_*` are untouched.

### Interfaces / classes

- **`TestKind(StrEnum)`** — closed kind set. Members/values: `NOT_NULL = "not_null"`,
  `UNIQUE = "unique"`, `ACCEPTED_VALUES = "accepted_values"`, `RELATIONSHIPS = "relationships"`.
  Mirrors `TransformationKind`: a named, importable type for the Transform layer / DANDER-8 to branch
  on, serializing to/from its plain string value; an out-of-set value fails at the Pydantic boundary.

- **`FieldTest(BaseModel)`** — one declarative generic test. `model_config =
  ConfigDict(populate_by_name=True)`.
  - `kind: TestKind` — the discriminator (no default; a test must name its kind).
  - `values: list[Any] = Field(default_factory=list)` — the accepted-values list. `list[Any]` matches
    the `Transformation.constant` JSON-literal precedent (tokens may be str/int/bool). Required
    non-empty when `kind is ACCEPTED_VALUES`; must be empty for every other kind.
  - `to: str | None = None` — referenced **node id** for `RELATIONSHIPS` (names only, never values).
  - `field: str | None = None` — referenced **field name** for `RELATIONSHIPS`.
  - `metadata: dict[str, Any] = Field(default_factory=dict)` — free-form tags only, never data/secrets
    (consistent with `NodeField.metadata` / `Node.config`).
  - `@model_validator(mode="after") _check_kind_params(self) -> FieldTest` — the boundary guard:
    - `ACCEPTED_VALUES`: require non-empty `values` (`if not self.values: raise ValueError(...)`);
      `to`/`field` must be unset.
    - `RELATIONSHIPS`: require `field` (`if self.field is None or not self.field.strip(): raise`);
      `values` must be empty. See the "note" below on whether `to` is also required.
    - `NOT_NULL` / `UNIQUE`: `values` empty and `to`/`field` unset.
    - Forbid-checks use value emptiness/`None` (`if self.values:` / `if self.to is not None:`), **not**
      `model_fields_set` — because none of these params has a meaningful "explicit empty/null" value
      (unlike `Transformation.constant`, whose legitimate `null` forced the `model_fields_set` dance).
      An empty `values` list and `None` `to`/`field` are the neutral defaults and dump/reload cleanly,
      so checking the value is lossless and dump→load round-trips without spurious failures.

- **`NodeField(BaseModel)`** — extended (backward compatible):
  - Add `cast_to: str | None = None` — optional target/cast type; `None` = no override.
  - Add `tests: list[FieldTest] = Field(default_factory=list)` — declarative generic tests; empty by
    default so a DANDER-4 field is unchanged.
  - `type` docstring clarified to "raw/source type"; new attributes get Google-style docstrings noting
    they are **declarative and executed downstream** (casting in the Writer, tests in the
    Transform/test-runner layer), never here.

Placement: define `TestKind` and `FieldTest` immediately **above** `NodeField` (a forward-ref/reorder
is required since `NodeField` now references `FieldTest`); `from __future__ import annotations` is
already present so annotation ordering is not an issue, but the classes should be defined before use
for readability, matching how `TransformationKind` precedes `Transformation`.

### Files to touch / create

- **`src/dander/pipeline/graph.py`** (edit) — add `TestKind`, `FieldTest` (+ validator), extend
  `NodeField` with `cast_to` and `tests`. No changes to `Node`, `Edge`, `PipelineGraph`, or the four
  load/dump functions. If a public `__all__` or `src/dander/pipeline/__init__.py` re-exports graph
  symbols, add `TestKind` and `FieldTest` there (check and keep in sync).
- **`tests/pipeline/test_field_casting_and_tests.py`** (create) — see test seams. Module docstring in
  the house style; synthetic field/type/token names only (`steering/01-security.md`).

### Test seams (unit only, no network, no mocks)

- **Load each kind from YAML and JSON**: a field with `cast_to` set; a field carrying one of each
  test kind (`not_null`, `unique`, `accepted_values` with a synthetic token list, `relationships`
  with `to`/`field`). Assert the parsed model values.
- **Boundary rejection** (expect `pydantic.ValidationError`): `accepted_values` with empty/omitted
  `values`; `relationships` missing `field`; a non-accepted_values kind carrying `values`; a
  non-relationships kind carrying `to`/`field`; an out-of-set `kind` string.
- **Round-trip stability** (AC5): build a `PipelineGraph` whose field has a `cast_to` + all four test
  kinds, `dump_graph_to_yaml`/`_json` → load → assert `model` equality (and dump→load→dump idempotence).
- **Backward compatibility** (AC4): a `NodeField(name=..., type=...)` with no `cast_to`/`tests` loads,
  equals its DANDER-4 shape (`cast_to is None`, `tests == []`), and round-trips by model equality.
- Nothing is mocked — these are pure in-memory Pydantic models and file round-trips through a
  `tmp_path`, matching `test_graph_fields.py`/`test_transformations.py`.

### Trade-offs

- **Additive `cast_to` vs. renaming `type`→`raw_type` (+ alias).** A rename with a `validation_alias`
  keeping `type` accepted would read more symmetrically (`raw_type`/`target_type`) but is more
  invasive, risks subtle backward-compat/serialization drift (dump key changes), and churns every
  existing caller/fixture of `NodeField.type`. The additive `cast_to` gives the same raw-vs-target
  capability with zero disruption. Chosen.
- **Single `FieldTest` + after-validator vs. a Pydantic discriminated union of one class per kind.**
  A `Field(discriminator="kind")` union of `NotNullTest`/`UniqueTest`/`AcceptedValuesTest`/
  `RelationshipsTest` would make illegal states unrepresentable at the type level. Rejected for
  consistency: this module already models `Transformation` (a comparable kind+params shape) as a
  single model with a payload validator, and matching that precedent keeps the codebase uniform and
  the downstream `match kind:` branch identical in style. (Noted as the reasonable alternative.)
- **`values: list[Any]` vs. `list[str]`.** `Any` mirrors `Transformation.constant` so accepted-values
  can be ints/bools, not only strings. Fixtures still use synthetic tokens only.

### Notes / flags for the Code agent

- **`RELATIONSHIPS.to` requiredness is slightly under-specified.** AC only hard-requires "its
  referenced field" (`field`). A relationships test with a `field` but no `to` (target node id) is
  structurally dangling. Recommendation: **require `field` (AC-mandated) and also require `to`**, since
  "referencing another node/field" names both and a field ref without a node is meaningless — but this
  is a judgment call; if the reviewer reads AC narrowly, relax `to` to optional. Implement as required
  with a clear message and a test either way; call it out in Implementation Notes.
- **Cross-node resolution is out of scope.** Whether a `relationships` test's `to`/`field` (or a
  `cast_to`) actually resolves against another node is DANDER-8-style lineage validation
  (`graph_ops.validate_field_wiring` already exists) — note it, do **not** implement it here.
- No casting execution, no test execution, no changes to load/dump. Keep the diff to the model +
  validator + tests. Run `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`,
  `uv run pytest` — all must stay green.

## Implementation Notes

Implemented exactly per the Design, no scope beyond the `NodeField` extension + validation +
serialization + tests.

- **`src/dander/pipeline/graph.py`**: added `TestKind(StrEnum)` (`NOT_NULL`, `UNIQUE`,
  `ACCEPTED_VALUES`, `RELATIONSHIPS`) and `FieldTest(BaseModel)` (`kind`, `values: list[Any]`,
  `to: str | None`, `field: str | None`, `metadata`), both defined immediately above `NodeField`
  as specified. `FieldTest._check_kind_params` (`@model_validator(mode="after")`) enforces the
  per-kind required/forbidden params, checking field **value** (not `model_fields_set`) so
  dump -> load stays lossless, matching the `Trigger`/`Transformation` precedent reasoning in the
  Design. `NodeField` gained `cast_to: str | None = None` (additive; `type` keeps its existing
  raw/source-type meaning) and `tests: list[FieldTest] = Field(default_factory=list)`; both
  default such that a DANDER-4 field is unchanged. Docstrings updated to note casting/tests are
  declarative and executed downstream only (Writer / Transform-test-runner layer respectively),
  never here.
- **`RELATIONSHIPS.to` requiredness** (flagged as under-specified in the Design): implemented as
  **required** alongside `field` — "referencing another node/field" names both, and a bare
  `field` with no `to` node is structurally dangling. Covered by
  `test_relationships_kind_rejects_missing_to`; flagging per the Design's request in case the
  reviewer reads the AC narrowly and wants `to` relaxed to optional.
- **No changes** to `Node`, `Edge`, `PipelineGraph`, the four load/dump functions, or
  `_dump_graph_payload` — the new attributes ride the existing `model_dump(by_alias=True,
  mode="json")` path with no special-casing needed, consistent with how `Edge.mappings`/
  `Node.fields` already dump `[]` defaults and `FieldMapping.source`/`.description` already dump
  `null` defaults.
- **`src/dander/pipeline/__init__.py`**: left untouched. Checked — it re-exports only the
  top-level container types (`Edge`, `Node`, `PipelineGraph`) and the load/dump functions; none of
  the existing sibling "sub-model" types on this module (`NodeField`, `Transformation`,
  `TransformationKind`, `Trigger`, `TriggerKind`, `FieldMapping`, `JoinSpec`, `JoinType`,
  `JoinKeyPair`) are re-exported there either, so adding `TestKind`/`FieldTest` would have broken
  that existing convention rather than kept it in sync. Tests import both directly from
  `dander.pipeline.graph`, matching `test_graph_fields.py`/`test_transformations.py`.
- **`tests/pipeline/test_field_casting_and_tests.py`** (new): covers load-from-YAML/JSON of a
  `cast_to` override and all four `FieldTest` kinds; YAML/JSON round-trip stability (model
  equality plus a dump -> load -> dump idempotence check); backward compatibility (a
  `NodeField(name=..., type=...)` loads/round-trips with `cast_to is None`/`tests == []`,
  unchanged from a DANDER-4 field); and boundary-constraint rejection for each kind (missing/empty
  `accepted_values.values`, missing `relationships.to`/`.field`, non-`accepted_values` kinds
  carrying `values`, non-`relationships` kinds carrying `to`/`field`, and an out-of-set `kind`
  string). No network; fixtures use synthetic type/token names only
  (`STRING`/`TIMESTAMP`/`applied`/`withdrawn`/`hired`/node ids `n1`/`n2`).
- **Out of scope, as directed**: no casting is applied, no test is executed, and cross-node
  resolution of `cast_to`/`relationships.to`/`.field` against real nodes/fields is not
  implemented — that remains DANDER-8-style lineage validation
  (`dander.pipeline.graph_ops.validate_field_wiring`).
- **Tooling**: `uv run ruff check`, `uv run ruff format --check` (after one auto-format pass),
  `uv run mypy`, and `uv run pytest` are all green for the touched files. A pre-existing
  `PytestCollectionWarning` fires because pytest's default discovery treats any class named
  `Test*` as a test class; `TestKind` is a plain `StrEnum` with no test methods, so this is
  cosmetic (not a failure) and the name was fixed by the ticket's Design for consistency with
  `TransformationKind`/`JoinType`/`TriggerKind`. Full-repo `ruff check .`/`mypy .` show pre-existing
  errors in unrelated, already-untracked WIP files from other in-flight tickets
  (`scripts/watch_workflows.py`, `tests/ingestion/test_rate_limit_config.py`,
  `tests/ingestion/test_pagination.py`) — confirmed via `git stash` that these predate this change
  and are outside this ticket's scope; `mypy`/`ruff` on the two files this ticket touches
  (`src/dander/pipeline/graph.py`, `tests/pipeline/test_field_casting_and_tests.py`) are clean, and
  the full `pytest` suite (223 tests) passes.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed the implementation in `src/dander/pipeline/graph.py` and
`tests/pipeline/test_field_casting_and_tests.py` against all acceptance criteria and the steering
files. Verdict: **PASS**.

- **AC1 (casting override, backward compatible):** `NodeField.type` retained as raw/source type;
  added `cast_to: str | None = None` for the target/cast override. A field declaring only `type`
  loads unchanged (`cast_to` defaults to `None`). Verified by
  `test_plain_field_with_no_cast_to_or_tests_is_unchanged`.
- **AC2 (generic tests, closed set, typed):** `TestKind(StrEnum)` with `not_null`/`unique`/
  `accepted_values`/`relationships`; single `FieldTest(BaseModel)` carries `kind`, `values`, `to`,
  `field`, `metadata`, fully type-annotated. `NodeField.tests: list[FieldTest]` default-empty.
- **AC3 (boundary constraints):** `FieldTest._check_kind_params` (`@model_validator(mode="after")`)
  enforces non-empty `values` for `accepted_values`, required `to`+`field` for `relationships`, and
  forbids cross-kind params, each with a clear `ValueError`. No test executed, no casting applied.
  Cross-node resolution explicitly deferred to DANDER-8 in docstrings.
- **AC4/AC5 (backward-compat + YAML/JSON round-trip):** covered by the round-trip and
  backward-compat tests, including dump→load→dump idempotence.
- **AC6 (docs/typing/security):** Google-style docstrings note casts/tests are declarative and
  executed downstream; fixtures use synthetic tokens only (`STRING`/`TIMESTAMP`/`applied`/
  `withdrawn`/`hired`, node ids `n1`/`n2`). No secrets or real sample values anywhere in the diff.
- **AC7 (pytest coverage):** 17 tests under `tests/pipeline/`, no network; cover load-of-each-kind
  (YAML+JSON), all boundary rejections (including out-of-set kind, missing `to`), round-trip
  stability, and the unchanged DANDER-4 field.
- **AC8 (tooling green):** verified on the touched files — `ruff check` and `ruff format --check`
  clean, `mypy src/dander/pipeline/graph.py` clean, `pytest tests/pipeline` all pass (the
  `PytestCollectionWarning` on `TestKind` is cosmetic — a `StrEnum`, not a test class — and matches
  the `TransformationKind`/`TriggerKind` naming convention).
- **Design fidelity / `__init__.py`:** the `RELATIONSHIPS.to` requiredness judgment call (required)
  is reasonable and tested. Not re-exporting `TestKind`/`FieldTest` from
  `src/dander/pipeline/__init__.py` is correct — that module re-exports only top-level container
  types and load/dump functions, no sibling sub-models (`NodeField`, `Transformation`, `Trigger`,
  etc.), so adding these would have broken the existing convention. Verified against the file.
- **Scope:** no casting execution, no test execution, no cross-node resolution, no load/dump
  changes — confined to the model + validator + tests as specified.

No blocking issues. Status set to `done`.
