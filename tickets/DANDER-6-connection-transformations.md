---
id: DANDER-6
title: Custom transformations on pipeline-graph connections
status: done
component: python
epic: pipeline
depends_on: [DANDER-5]
created: 2026-07-22
---

## Context

A field-to-field mapping (DANDER-5) is a direct copy. The request also needs **custom
transformations supported at each connection** — a target field computed from source field(s) by an
expression (cast, concat, coalesce, rename-with-logic), a constant/default value, or a derived field
that has no single source column. This ticket makes a connection's mappings **transformable**.

This stays declarative and model-only: a transformation is captured as a **kind + expression**
(e.g. a `direct` copy, an `expression` string, or a `constant`) attached to a mapping and/or to the
edge for derived fields. Dander does **not** execute or evaluate the expression here — parsing,
compiling, and running it belong to the Transform/Writer layers per
`steering/00-project-overview.md`. Storing an expression as an opaque, declarative string keeps this
in scope and provider-agnostic.

Security note: an expression is authored logic, not data — but it must never embed a secret or
credential literal (`steering/01-security.md`); the expression references fields and functions, and
secrets stay in Secret Manager / env. Validation that a transformation's referenced input fields
exist is DANDER-8.

## Acceptance Criteria

- [ ] A declarative transformation representation attachable to a `FieldMapping` (and, where a
      derived/computed target field has no single source field, expressible at the edge/mapping
      level). It captures at minimum a **kind** (e.g. `direct`/`expression`/`constant`) and the
      associated payload (an expression string for `expression`, a literal for `constant`), plus
      optional free-form `metadata`. A plain DANDER-5 direct mapping remains expressible and is the
      default when no transformation is given (backward compatible).
- [ ] The model captures the transformation's **input field references** (zero or more source field
      names) so a later validation pass (DANDER-8) can check they resolve — without evaluating the
      expression here.
- [ ] Transformations round-trip stably through **both** YAML and JSON via the existing load/dump
      functions: load → dump → load yields an equivalent graph (model equality), including
      `expression` and `constant` kinds and a mapping with no transformation.
- [ ] Any intra-model constraints are enforced at the Pydantic boundary (e.g. an `expression` kind
      requires a non-empty expression; a `constant` kind requires its literal) and raise a clear
      validation error. No expression evaluation/execution occurs in this ticket.
- [ ] Google-style docstrings on new/changed public models; fully type-annotated per
      `steering/languages/python.md`. Docstrings state that expressions are opaque/declarative here
      and evaluated downstream. No secrets in expressions, defaults, or test fixtures.
- [ ] pytest tests cover: an edge/mapping loads a `direct`, an `expression`, and a `constant`
      transformation from YAML and JSON; all round-trip stably in both formats; input-field
      references survive the round-trip; and the boundary constraints reject a malformed
      transformation (e.g. `expression` kind with an empty expression). Tests live under `tests/`
      and require no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the transformation model + serialization + boundary
      constraints and their tests (no expression parsing/evaluation; no cross-node field-existence
      validation — that is DANDER-8).

## Design

### Approach

This ticket makes a connection's field mappings *transformable* by adding one small, declarative
value object — a `Transformation` — that a `FieldMapping` (delivered by DANDER-5) can carry. It is
**model + serialization only**: a transformation captures a `kind` plus its declarative payload
(an opaque `expression` string, or a `constant` literal) and the list of source-field names it
references. Nothing here parses, compiles, or evaluates an expression — that is the Transform/Writer
layer's job per `steering/00-project-overview.md`. Storing the expression as an opaque string keeps
this in scope and provider-agnostic.

The design lives entirely in `src/dander/pipeline/graph.py`, alongside `Node`/`Edge`/`PipelineGraph`
(and the DANDER-5 `FieldMapping`), because the existing `load_*`/`dump_*` functions already recurse
the whole Pydantic model tree — **no changes to `graph_ops.py` or the four load/dump functions are
needed**; adding a nested model round-trips through YAML and JSON for free. This is the same reason
DANDER-4/DANDER-5 add their models here.

Backward compatibility is the default: `FieldMapping.transformation` defaults to `None`, which means
a plain DANDER-5 direct field-to-field copy — an edge/mapping authored before this ticket loads and
dumps unchanged.

### Interfaces / classes

**`TransformationKind(StrEnum)`** — the closed set of transformation kinds:
`DIRECT = "direct"`, `EXPRESSION = "expression"`, `CONSTANT = "constant"`. A `StrEnum` (not a bare
`Literal`) so the Transform/Writer layer and DANDER-8 can branch on a named, importable type while it
still serializes to/from its plain string value stably in YAML and JSON. Extensible by adding a
member later without touching callers.

**`Transformation(BaseModel)`** — the declarative transformation attached to a mapping:
- `kind: TransformationKind = TransformationKind.DIRECT` — the discriminator.
- `expression: str | None = None` — opaque, declarative expression string for `EXPRESSION` kind
  (e.g. `"CONCAT(first_name, ' ', last_name)"`). Never evaluated here.
- `constant: Any = None` — the literal payload for `CONSTANT` kind. Typed `Any` (with a justifying
  comment, matching the existing `Node.config` precedent) because a constant is arbitrary JSON —
  str/int/float/bool/null/list/dict. Presence is checked via `model_fields_set` (see constraints) so
  a legitimate constant `null` is distinguishable from "not provided."
- `inputs: list[str] = Field(default_factory=list)` — zero or more **source-field names** the
  transformation references, so DANDER-8 can later check they resolve. Names only, never values.
- `metadata: dict[str, Any] = Field(default_factory=dict)` — optional free-form tags.
- `model_config = ConfigDict(populate_by_name=True)` for consistency with the sibling models. No
  field aliases are needed — the on-disk keys are `kind`/`expression`/`constant`/`inputs`/`metadata`.

**Intra-model constraints** — a single `@model_validator(mode="after")` on `Transformation`:
- `EXPRESSION` kind → `expression` must be present and non-empty (after `.strip()`); `constant` must
  not be set.
- `CONSTANT` kind → `constant` must be present (checked with `"constant" in self.model_fields_set`,
  which permits a `null` literal but rejects an omitted one); `expression` must be `None`.
- `DIRECT` kind → neither `expression` nor `constant` is set.
- Each violation raises a `ValueError` inside the validator (surfaced by Pydantic as a
  `ValidationError`) with a clear, secret-free message naming the kind and the missing/forbidden
  field. No expression evaluation occurs.

**`FieldMapping` (DANDER-5) — extended by this ticket, two changes:**
- Add `transformation: Transformation | None = None`. `None` = plain direct copy (backward
  compatible default). An explicit `Transformation(kind=DIRECT)` is also accepted (redundant but
  legal; both round-trip).
- Relax `source_field` from required to `str | None = None`, so a **derived/computed** target field
  with no single source column is expressible as a mapping whose `source_field` is `None` and whose
  `transformation` supplies the logic (its `inputs` list carries any referenced source fields).
  Add a `@model_validator(mode="after")` on `FieldMapping`: if `source_field is None` then a
  `transformation` of kind `EXPRESSION` or `CONSTANT` is **required** — a mapping that names neither a
  source column nor a transformation produces nothing and is rejected at the boundary.

### Files to touch / create

- `src/dander/pipeline/graph.py` — add `TransformationKind`, `Transformation` (with its validator),
  and extend `FieldMapping` (add `transformation`, relax `source_field`, add its validator). Import
  `StrEnum` from `enum` and `model_validator` from `pydantic`. Google-style docstrings on every new/
  changed public model stating that expressions/constants are **opaque and declarative here,
  evaluated downstream**, and that neither an expression nor a constant may embed a secret.
- `src/dander/pipeline/__init__.py` — export `Transformation` and `TransformationKind` if the package
  re-exports the DANDER-5 mapping symbols (mirror whatever DANDER-5 does; keep it consistent).
- `tests/pipeline/test_transformations.py` (new) — the DANDER-6 test suite (see Test seams). Kept
  separate from `test_graph.py`/the DANDER-5 mapping tests for cohesion.

### Test seams

Pure model + Pydantic validation + the existing file load/dump using `tmp_path`. No network, no
mocking (no I/O beyond temp files), no secrets or real data in fixtures. Cover:
- A mapping loads a `direct`, an `expression`, and a `constant` transformation from **YAML** and from
  **JSON** (small inline docs, `tmp_path`, `load_graph_from_yaml`/`load_graph_from_json`).
- Round-trip stability in **both** formats: `load → dump → load` yields model equality, for each of
  the three kinds and for a mapping with **no** transformation (backward compat).
- `inputs` (source-field references) survive the round-trip.
- Boundary constraints raise `pydantic.ValidationError`: `EXPRESSION` kind with an empty/missing
  expression; `CONSTANT` kind with no literal provided; a derived mapping (`source_field=None`) with
  no transformation. Assert via `pytest.raises(ValidationError)`.
- Fixtures use benign logic only, e.g. expression `"CONCAT(first_name, ' ', last_name)"`, constant
  `"active"`, inputs `["first_name", "last_name"]` — no values, no secrets.

### Trade-offs

- **`StrEnum` over `Literal["direct","expression","constant"]`** — a named, importable closed set the
  Transform layer and DANDER-8 branch on; still serializes as a plain string. Slightly heavier than a
  `Literal`, worth it for discoverability and safe extension.
- **`constant` presence via `model_fields_set` over "non-null required"** — lets a genuine constant
  `null` be expressed while still rejecting an omitted literal. Costs one line in the validator vs. a
  simpler-but-wrong `constant is not None` check.
- **Optional `source_field` on `FieldMapping` over a separate edge-level transformations list** —
  keeps transformations in one place (the mapping), so there is one concept to serialize and reason
  about; a derived field is just a mapping with no source column. Avoids a second parallel collection
  on `Edge`.
- **Models in `graph.py` over a new `field_mapping.py` module** — matches the established pattern
  (all graph-shape models colocate with the load/dump functions), and keeps the round-trip free. If
  `graph.py` grows unwieldy across the epic, splitting the mapping/transformation models into their
  own module is a clean later refactor.
- **No `direct`-payload storage / no evaluation** — a `direct` transformation carries no expression;
  evaluation of any kind is explicitly deferred to Transform/Writer (scope discipline).

### Notes / flags for the Code agent

- **Depends on DANDER-5.** This ticket *modifies* the DANDER-5 `FieldMapping` (adds `transformation`,
  relaxes `source_field` to optional, adds a mapping-level validator). If DANDER-5 shipped
  `source_field` as strictly required, that is the intended, in-scope change here — coordinate so the
  DANDER-5 mapping tests still pass (a mapping *with* a source field and no transformation must remain
  valid and unchanged on disk).
- The on-disk key names for the mapping's source/target fields are owned by DANDER-5; this design
  nests the transformation under a `transformation:` key and does not redefine them.
- Security: an expression/constant is authored logic, never data. Docstrings must say so, and no
  fixture may contain a secret or credential literal (`steering/01-security.md`). Field-existence
  validation of `inputs` is DANDER-8 and out of scope here.

## Implementation Notes

Implemented per Design, entirely in `src/dander/pipeline/graph.py`:

- Added `TransformationKind(StrEnum)` (`DIRECT`/`EXPRESSION`/`CONSTANT`) and `Transformation`
  (`kind`, `expression`, `constant: Any`, `inputs: list[str]`, `metadata`), with a
  `@model_validator(mode="after")` enforcing the payload each kind requires/forbids.
- Extended `FieldMapping` (DANDER-5's model, whose on-disk keys are `source`/`target`, not
  `source_field`/`target_field` as the Design's prose names them — the Design's own Files-to-touch
  section and existing tests confirm `source`/`target` are the real attribute names, so that's what
  was relaxed): `source: str | None = None` (was required) and a new
  `transformation: Transformation | None = None`, plus a `@model_validator(mode="after")` requiring
  an `EXPRESSION`/`CONSTANT` transformation whenever `source is None` (a derived field).
- `pipeline/__init__.py` left unchanged: `FieldMapping`/`NodeField` are not re-exported there
  (confirmed by grep), so per the Design's "mirror whatever DANDER-5 does" instruction,
  `Transformation`/`TransformationKind` are not added to the package `__all__` either — consistent,
  not a gap.
- New test module `tests/pipeline/test_transformations.py` (17 tests): load from YAML/JSON for all
  three kinds, YAML+JSON round-trip stability (including `inputs`), a no-transformation mapping
  round-tripping unchanged (DANDER-5 backward compat), an explicit `Transformation(kind=DIRECT)`
  round-tripping, and `pytest.raises(ValidationError)` coverage for every boundary constraint
  (empty/missing expression, constant+expression both set, missing constant, explicit `constant:
  null` accepted, a derived mapping with no/wrong-kind transformation).

**Deviation found and fixed during implementation (design bug, not a scope change):** the Design's
`Transformation` validator, as specified, checked "must not set `constant`" for `DIRECT`/
`EXPRESSION` via `"constant" in self.model_fields_set` — the same presence check prescribed for the
`CONSTANT`-requires-a-literal side. That breaks the round-trip acceptance criterion: `model_dump`
(used by `dump_graph_to_yaml`/`_json`) always serializes every field, including a default
`constant: null`, so after one dump → load cycle *any* kind's reloaded model has `constant` in
`model_fields_set`, and `DIRECT`/`EXPRESSION` transformations would spuriously fail their own
just-passed validation on reload. Fixed by keeping the presence-based check only for the
`CONSTANT`-requires-a-literal side (so an authored `constant: null` still round-trips as
"provided"), and switching the two prohibition checks to a value check (`self.constant is not
None`) — lossless, since a `constant` value of `None` is never meaningful outside the `CONSTANT`
kind. Documented in the validator's docstring. Caught by
`test_yaml_round_trip_is_stable_with_transformations` /
`test_json_round_trip_is_stable_with_transformations` /
`test_explicit_direct_transformation_is_legal_and_round_trips`, all of which failed before the fix
and pass after.

**Pre-existing test updated (expected, flagged by Design):** `test_field_mapping_on_disk_keys_
are_source_and_target` in `tests/pipeline/test_graph.py` (DANDER-5) asserted an exact `model_dump()`
dict with no `transformation` key; updated its expected dict to include `"transformation": None`,
the correct new default. No other DANDER-5 assertion needed a change — all other mapping/edge dump
assertions in that file check substrings or dumps with empty `mappings: []`, unaffected by the new
field.

No changes to `graph_ops.py` or the four load/dump functions, as anticipated — the nested
`Transformation` model round-trips through the existing recursive Pydantic dump/validate for free.

**Toolchain:** `uv run ruff check src tests`, `uv run ruff format --check src tests`,
`uv run mypy src tests`, and `uv run pytest -q` all green (63 tests pass, including the 17 new
DANDER-6 tests). Note: `uv run ruff check .` (whole repo) fails on a pre-existing, unrelated
`E501` in `scripts/watch_workflows.py` that predates this ticket (confirmed via `git stash`) and is
out of scope here.

## Review Log

_Append-only. PR-Review adds entries below._

- 2026-07-22 — **PASS** — Reviewed implementation in `src/dander/pipeline/graph.py` and tests in
  `tests/pipeline/test_transformations.py` (+ the DANDER-5 update in `tests/pipeline/test_graph.py`)
  against all acceptance criteria and steering.
  - **AC1 (declarative transformation on FieldMapping, derived at mapping level, kind+payload+metadata,
    direct default):** met. `Transformation(kind/expression/constant/inputs/metadata)` +
    `FieldMapping.transformation: Transformation | None = None` (default None = direct copy). Derived
    fields expressible via `source=None` + a required EXPRESSION/CONSTANT transformation.
  - **AC2 (input field references):** met — `inputs: list[str]`, names only, survive round-trip
    (asserted in the YAML/JSON round-trip tests).
  - **AC3 (round-trip through YAML and JSON):** met — model-equality round-trip tests for all three
    kinds plus a no-transformation mapping, in both formats.
  - **AC4 (boundary constraints, no evaluation):** met — `@model_validator(mode="after")` enforces
    EXPRESSION⇒non-empty expression / no constant, CONSTANT⇒literal present (via `model_fields_set`,
    permitting explicit null) / no expression, DIRECT⇒neither; clear secret-free `ValueError`s. No
    expression parsing/evaluation anywhere.
  - **AC5 (docstrings/typing/no secrets):** met — Google-style docstrings on every new/changed public
    model, fully type-annotated, docstrings state expressions/constants are opaque & evaluated
    downstream and must not embed secrets. Diff scan found no credential-shaped literals (only the
    security-note prose); fixtures use benign synthetic logic.
  - **AC6 (tests):** met — 17 network-free tests under `tests/`, covering load from YAML+JSON for all
    kinds, round-trip stability incl. `inputs`, backward-compat, and `ValidationError` for every
    malformed case.
  - **AC7 (toolchain green):** verified locally — `ruff check src tests`, `ruff format --check`,
    `mypy src tests` (31 files, no issues), `pytest` (63 passed). The pre-existing whole-repo
    `ruff check .` E501 in `scripts/watch_workflows.py` is unrelated and out of scope.
  - **AC8 (no scope creep / steering):** met — model + serialization + boundary constraints only; no
    evaluation, no DANDER-8 field-existence checks; no `graph_ops.py`/load-dump changes.
  - **Design fidelity:** matches the approved design; the one deviation (constant-prohibition checks
    use value-comparison rather than `model_fields_set` to keep DIRECT/EXPRESSION round-tripping) is a
    genuine design-bug fix, documented in Implementation Notes and the validator docstring, and is
    lossless. The `source`/`target` on-disk key naming (vs. the design prose's `source_field`) is the
    real DANDER-5 attribute name; the change relaxed the correct field. `pipeline/__init__.py`
    non-export mirrors DANDER-5 (FieldMapping/NodeField aren't re-exported either) — confirmed.
  - No blocking issues. Status → done.
