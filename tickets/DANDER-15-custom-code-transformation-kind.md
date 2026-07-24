---
id: DANDER-15
title: Custom-code transformation kind referencing an allow-listed function
status: done
component: python
epic: pipeline-config
depends_on: []
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (see DANDER-10 for the shared
review context).

`Transformation.kind` in `src/dander/pipeline/graph.py` (delivered by DANDER-6) supports only
`direct` / `expression` / `constant`. Genuinely novel logic that cannot be expressed as a
declarative expression has no home. `steering/02-engineering.md` says to "reserve code for genuinely
novel logic" — but `steering/01-security.md` forbids executing arbitrary strings, which would be a
code-injection surface.

This ticket adds a `CUSTOM_CODE` (or similarly named) transformation kind that references a
**registered / allow-listed function by name** — never an eval'd or inline code string. The model
stores only a function-registry key (and any declared arguments as field references / literals),
mirroring how auth strategies are referenced by a registered key. Resolving and invoking the
function belongs to the Transform/Writer layer; nothing is executed here.

## Acceptance Criteria

- [ ] `TransformationKind` gains a `CUSTOM_CODE` (or similarly named) member, and `Transformation`
      can carry the payload it needs: a **function-registry name/key** plus optional declared
      arguments. Existing `direct`/`expression`/`constant` behavior is unchanged and backward
      compatible.
- [ ] The payload references a function **by name only** — the model must not accept or store an
      inline code string / lambda / eval-able source. This is enforced at the Pydantic boundary and
      stated in the docstring (`steering/01-security.md` — no arbitrary-string execution surface).
- [ ] Boundary constraints: a `CUSTOM_CODE` transformation requires a non-empty function name and
      forbids the `expression`/`constant` payloads of the other kinds (mirroring the existing kind
      validator), raising a clear validation error. No function is resolved or invoked here.
- [ ] The custom-code transformation round-trips stably through YAML and JSON via the existing
      load/dump functions (load → dump → load model equality), alongside the existing kinds.
- [ ] Google-style docstrings state the function is referenced by registry name and resolved/executed
      downstream, never here; typed per `steering/languages/python.md`. No secrets/inline code in
      fixtures.
- [ ] pytest tests cover: a `CUSTOM_CODE` transformation loads from YAML and JSON; round-trip
      stability; the boundary constraints reject a missing function name and reject the other kinds'
      payloads on a custom-code transformation; and the existing kinds are unaffected. Tests live
      under `tests/`, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the new kind + its payload + validation + serialization
      + tests. No function registry runtime, no resolution, no execution.

## Design

### Approach

Extend the existing `Transformation`/`TransformationKind` pair in
`src/dander/pipeline/graph.py` — do **not** add a new module. This is a small, additive change
that follows the exact pattern DANDER-6 already established for `EXPRESSION`/`CONSTANT`: a new
closed-enum member plus new declarative payload fields on the inert `Transformation` model, all
validated at the Pydantic boundary. The model stays opaque and inert — nothing is resolved,
looked up, or executed here. Resolving the referenced function and invoking it belongs entirely
to the future Transform/Writer layer (mirrors how DANDER-6 stores an `expression` string it
never evaluates, and how auth strategies are referenced by a registry key in the Security
module).

Two payload fields are added to `Transformation`:

- `function: str | None = None` — the **function-registry key/name only**. It is typed `str`
  (never `Callable`), so Pydantic already rejects a lambda/callable at the boundary. A
  `field_validator` additionally constrains the string to a dotted-identifier shape
  (`^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$`, compiled once at module scope as
  `_FUNCTION_KEY_PATTERN`). That pattern structurally excludes an inline code string / eval-able
  source: anything containing spaces, parentheses, operators, quotes, colons, or newlines
  (`lambda x: x`, `eval("...")`, `a + b`, `import os`) fails to match and raises a clear
  `ValueError`. This is the concrete enforcement of the security criterion ("referenced by name
  only — no arbitrary-string execution surface", `steering/01-security.md`).
- `arguments: dict[str, Any] = Field(default_factory=dict)` — optional declared arguments passed
  to the referenced function: a name→value mapping whose values are literals or field-reference
  tokens (names, never secret values — `steering/01-security.md`). Any source-field references an
  argument names should also be listed in the existing `inputs` field so the deferred DANDER-8
  validation pass can resolve them; this reuses the established `inputs` convention rather than
  inventing a parallel one.

The `TransformationKind` enum gains `CUSTOM_CODE = "custom_code"`.

**Validation** extends the existing `_check_kind_payload` `model_validator(mode="after")`,
keeping its established "check value, not presence" discipline (so dump→load stays stable
because `model_dump` always serializes every field):

- New `CUSTOM_CODE` branch: requires `function` to be present and non-empty
  (`self.function is None or not self.function.strip()` → error), and forbids the other kinds'
  payloads — reject `expression is not None` and `constant is not None`. It **permits**
  `arguments` (that is CUSTOM_CODE's own payload).
- The existing `DIRECT`/`EXPRESSION`/`CONSTANT` branches each additionally forbid the new
  CUSTOM_CODE payload: reject `function is not None` and a non-empty `arguments` (truthiness
  check — an empty `{}` is the default and must pass so it survives round-trips). This mirrors how
  those branches already forbid each other's payloads.

**Serialization** needs **no** change to `_dump_graph_payload`/`dump_graph_to_*`/`load_graph_*`.
Since DANDER-6, every `Transformation` is already dumped with its full field set (`expression:
null`, `constant: null`, `inputs: []`, `metadata: {}`) and reloads to an equal model — the only
special-cased omission is a join-less edge's `join` key (a field edges predated). Adding
`function: null` and `arguments: {}` to every dumped transformation follows that same established,
round-trip-stable behavior. The "check value not presence" validator design is exactly what keeps
a dumped `function: null` / `constant: null` from spuriously tripping the forbid-checks on reload.

**FieldMapping derived-field rule (in scope — one-line extension):**
`_check_derived_mapping_has_transformation` currently allows a `source=None` (derived) mapping
only when its transformation kind is `EXPRESSION` or `CONSTANT`. A `CUSTOM_CODE` transformation can
equally produce a derived value with no single source column, so `CUSTOM_CODE` is added to that
allowed set. Without this, a custom-code derived field could not be authored — an inconsistency,
not new behavior. (A `CUSTOM_CODE` transformation attached to a mapping that *does* have a
`source` also remains valid.)

### Interfaces / classes (all in `src/dander/pipeline/graph.py`)

- **`TransformationKind(StrEnum)`** — add `CUSTOM_CODE = "custom_code"` plus a docstring
  `Attributes` line: "references an allow-listed function by registry name; resolved/executed
  downstream, never here."
- **`Transformation(BaseModel)`** — add fields `function: str | None = None` and
  `arguments: dict[str, Any] = Field(default_factory=dict)`; extend the class docstring's
  `Attributes` and the class-level security note (function referenced by name only, no inline
  code/lambda/eval source; arguments are literals/field-name references, never secret values).
  - `field_validator("function")` (new) — pass `None` through; else require the stripped value to
    be non-empty and to match `_FUNCTION_KEY_PATTERN`, raising `ValueError` otherwise.
  - `_check_kind_payload` (extend) — add the `CUSTOM_CODE` branch and add
    `function`/`arguments` prohibitions to the existing branches, per the Validation notes above;
    update its `Raises:` docstring.
- **`_FUNCTION_KEY_PATTERN`** — module-level `re.compile(...)` constant (add `import re`).
- **`FieldMapping._check_derived_mapping_has_transformation`** — add `TransformationKind.CUSTOM_CODE`
  to the allowed-kinds tuple and to the error-message wording; update the method docstring.

### Files to touch / create

- `src/dander/pipeline/graph.py` — all model/validator/docstring changes above. No new module.
- `tests/pipeline/test_transformations.py` — add CUSTOM_CODE cases (see Test seams). No new file
  needed; it already houses the `Transformation` suite and its YAML/JSON fixtures.

### Test seams

Pure in-memory model + serialization tests; no network, no mocking (matches the existing suite).
Add to `tests/pipeline/test_transformations.py`:

- **Load from YAML and from JSON**: extend the fixtures (or add a small dedicated fixture) with a
  `custom_code` mapping, e.g. `function: transforms.normalize_phone`,
  `arguments: {country: US}`, `inputs: [phone]`; assert kind/function/arguments/inputs parse.
- **Round-trip stability** (YAML and JSON): load → dump → load equality for a graph containing a
  `CUSTOM_CODE` mapping alongside the existing kinds.
- **Boundary — missing function**: `Transformation(kind=CUSTOM_CODE)` (no `function`) raises
  `ValidationError`; also `function=""` / `function="   "` raise.
- **Boundary — inline-code rejected**: `function="lambda x: x"` (and e.g. `function="eval('x')"`)
  raise `ValidationError` via the pattern — proves the no-eval-source guarantee.
- **Boundary — forbids other kinds' payloads on CUSTOM_CODE**:
  `Transformation(kind=CUSTOM_CODE, function="f", expression="UPPER(x)")` and
  `(..., function="f", constant="y")` each raise.
- **Boundary — other kinds forbid the function payload**:
  `Transformation(kind=EXPRESSION, expression="UPPER(x)", function="f")` and a `DIRECT` with
  `function="f"` (and a non-empty `arguments`) raise.
- **Existing kinds unaffected**: the DANDER-6 assertions (empty `arguments`/`None` `function` on
  `direct`/`expression`/`constant`) still hold; the pre-existing tests must stay green unchanged.
- **Derived custom-code mapping**: `FieldMapping(target="t", transformation=Transformation(
  kind=CUSTOM_CODE, function="f"))` (source=None) is accepted.

Fixtures use benign synthetic identifiers only (`transforms.normalize_phone`) — no secrets, no
inline code, no real data (`steering/01-security.md`).

### Trade-offs

- **Extend `Transformation` vs. a new payload model / subclass** — chosen: extend, because
  DANDER-6 already models `EXPRESSION`/`CONSTANT` as sibling optional fields on one flat model
  guarded by one `model_validator`. A discriminated-union refactor would be a larger, riskier
  change to a shipped model for no acceptance-criteria benefit; it would also churn the stable
  on-disk format. Consistency with the established shape wins.
- **`function` as a constrained `str` vs. a richer reference object** — chosen: plain constrained
  string, matching how auth strategies / expressions are referenced by a single key. The regex is
  the security boundary; a nested object adds no value while the registry itself is out of scope.
- **Regex allow-list vs. deny-list of dangerous chars** — chosen: allow-list (identifier/dotted
  path). An allow-list is the safe default for an injection-adjacent surface: it admits only known
  registry-key shapes rather than trying to enumerate everything malicious.
- **Reuse `inputs` for field references vs. deriving them from `arguments`** — chosen: reuse
  `inputs`. It already exists precisely so DANDER-8 can resolve referenced field names; parsing
  field refs back out of `arguments` values would duplicate that and couple this inert model to
  argument semantics it should not interpret.

### Notes / flags for the Code agent

- No `_dump_graph_payload` change is required or wanted — confirm by round-trip test, not by
  adding omission logic (adding `exclude_none`-style handling would regress the `constant: null`
  fix, see the existing regression tests).
- The `CUSTOM_CODE` extension to `FieldMapping._check_derived_mapping_has_transformation` is
  treated as in scope (it completes the kind rather than adding new behavior). If PR-Review reads
  the scope line more strictly, this is the one judgment call — it is called out here deliberately.
- Keep `mypy --strict` clean: `function: str | None`, `arguments: dict[str, Any]` (the `Any` is
  justified by the existing `constant`/`config` precedent — arbitrary JSON literal values).

## Implementation Notes

Implemented exactly per the Design section, all in `src/dander/pipeline/graph.py` — no new
module, no `_dump_graph_payload` change.

- **`TransformationKind`**: added `CUSTOM_CODE = "custom_code"` with an `Attributes` docstring
  line matching the established style.
- **`_FUNCTION_KEY_PATTERN`**: new module-level `re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_]
  [A-Za-z0-9_]*)*$")` constant (added `import re`), documented with the allow-list-vs-deny-list
  rationale from the Design's Trade-offs section.
- **`Transformation`**: added `function: str | None = None` and
  `arguments: dict[str, Any] = Field(default_factory=dict)`; extended the class docstring's
  `Attributes` and security note. Added `field_validator("function")` (`_check_function_shape`)
  that passes `None` through and otherwise requires the stripped value to be non-empty and match
  `_FUNCTION_KEY_PATTERN`, raising `ValueError` otherwise (rejects `"lambda x: x"`, `"eval('x')"`,
  `"a + b"`, `"import os"`, etc.).
- **`_check_kind_payload`**: added the `CUSTOM_CODE` branch (requires non-empty `function`;
  forbids `expression`/`constant`; permits `arguments`) and added `function`/`arguments`
  prohibitions to the `EXPRESSION`/`CONSTANT`/`DIRECT` branches, using the same
  value-not-presence discipline as the existing checks (`arguments` checked by truthiness so the
  default `{}` survives dump -> load; `function` checked by `is not None`). Updated the
  docstring's `Raises:` section.
- **`FieldMapping._check_derived_mapping_has_transformation`**: added `TransformationKind.
  CUSTOM_CODE` to the allowed-kinds tuple for a `source=None` derived mapping and updated the
  docstring/error message, per the Design's explicitly-flagged one-line extension.
- No change to `_dump_graph_payload`/`dump_graph_to_yaml`/`dump_graph_to_json`/
  `load_graph_from_yaml`/`load_graph_from_json` — confirmed by the new round-trip tests, not by
  adding omission logic (per the Notes-for-Code-agent flag).

**Tests** (`tests/pipeline/test_transformations.py`):

- Extended `_YAML_DOC`/`_JSON_DOC` with a fourth mapping using a `custom_code` transformation
  (`function: transforms.normalize_phone`, `arguments: {country: US}`, `inputs: [phone]`) and
  extended `_assert_expected_graph` to check it; the existing load tests now cover it for free.
- Added `test_yaml_round_trip_is_stable_with_custom_code` /
  `test_json_round_trip_is_stable_with_custom_code` asserting load -> dump -> load equality with
  the `CUSTOM_CODE` mapping in place.
- Added boundary tests: missing/empty `function` on `CUSTOM_CODE`; inline-code-shaped `function`
  values rejected (`lambda x: x`, `eval('x')`, `a + b`, `import os`); `CUSTOM_CODE` forbids
  `expression`/`constant`; `EXPRESSION`/`CONSTANT`/`DIRECT` forbid `function`
  (`DIRECT` also forbids non-empty `arguments`); a derived (`source=None`) `FieldMapping` accepts
  a `CUSTOM_CODE` transformation.
- Fixtures use only the benign synthetic identifier `transforms.normalize_phone` and literal
  `{"country": "US"}` — no secrets, no inline code, no real data.

**Tooling**: `uv run ruff check` and `uv run ruff format --check` (after `ruff format` fixed two
line-length wraps introduced by the new docstrings/tests) both clean on the touched files;
`uv run mypy src/dander/pipeline/graph.py` clean; `uv run pytest tests/pipeline/test_transformations.py`
— all 31 tests pass. Also ran the full suite (`uv run pytest -q`) — 217 passed. A full-repo
`ruff check`/`mypy` surfaced 1 pre-existing `E501` and 2 pre-existing `type-arg` findings in
`scripts/watch_workflows.py`; confirmed via `git stash` that these predate this change and are
unrelated to this ticket's scope — not touched.

No deviations from the Design. The one called-out judgment call (extending
`_check_derived_mapping_has_transformation` for `CUSTOM_CODE`) was implemented as the Design
recommends, since it completes the existing kind-parity behavior rather than adding new scope.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed the implementation in `src/dander/pipeline/graph.py` and
`tests/pipeline/test_transformations.py` against all acceptance criteria and the steering files.

- **Acceptance criteria — all met.** `TransformationKind.CUSTOM_CODE` added; `Transformation`
  carries `function: str | None` + `arguments: dict[str, Any]`; existing `direct`/`expression`/
  `constant` behavior unchanged (all DANDER-6 tests still green). Function is referenced by name
  only — typed `str` (never `Callable`) and constrained by the module-level allow-list
  `_FUNCTION_KEY_PATTERN` via `_check_function_shape`, which structurally rejects `lambda x: x`,
  `eval('x')`, `a + b`, `import os` (tested). The `CUSTOM_CODE` branch of `_check_kind_payload`
  requires a non-empty `function` and forbids `expression`/`constant`; the other branches forbid
  `function`/non-empty `arguments`. Nothing is resolved or executed. YAML/JSON round-trip stability
  holds with no `_dump_graph_payload` change, confirmed by the new round-trip tests (the
  value-not-presence validator discipline keeps a dumped `function: null`/`arguments: {}` from
  tripping the forbid-checks on reload).
- **Security — clean.** No hardcoded secrets/tokens in the diff (grep of the diff surfaced only
  security-note docstrings). Fixtures use the benign synthetic identifier
  `transforms.normalize_phone` and literal `{"country": "US"}` — no secrets, no inline code, no real
  data. The no-arbitrary-string-execution requirement is enforced at the Pydantic boundary and
  documented, satisfying `steering/01-security.md`.
- **Design fidelity — faithful.** Implemented exactly as the approved Design specifies; the single
  flagged judgment call (adding `CUSTOM_CODE` to `FieldMapping._check_derived_mapping_has_
  transformation`) completes kind-parity rather than adding new behavior and is in scope.
- **Language conventions & tooling — green.** Google-style docstrings, full typing (the `Any` on
  `arguments` mirrors the existing `constant`/`config` precedent). `uv run ruff check`,
  `uv run ruff format --check`, and `uv run mypy src/dander/pipeline/graph.py` all pass; full
  `uv run pytest` is green at **217 passed** (31 in the transformations suite).

No blocking issues. Status set to `done`.
