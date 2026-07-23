---
id: DANDER-7
title: Join specification on connections that combine data sources
status: done
component: python
epic: pipeline
depends_on: [DANDER-4]
created: 2026-07-22
---

## Context

The request asks for field-to-field mapping "when **joining** data sources together." Field mapping
(DANDER-5) is projection/lineage — it says which column becomes which — but it does **not** say how
two sources' rows are combined. Joining requires a **join predicate**: which field(s) on each side
are the join keys, and the join **type** (inner/left/right/full). Without this a graph can name the
fields that flow but can't express the join itself — this is the piece the request implies but
doesn't spell out, so it is added here.

This ticket adds a declarative **join specification** to a connection that combines sources: a join
type plus one or more key-field pairs (left field ↔ right field). It is model + serialization only,
declarative, and provider-agnostic — no SQL is generated and no join is executed here (that is the
Transform layer, per `steering/00-project-overview.md`). Cross-node validation that the join keys
reference fields declared on the joined nodes is DANDER-8.

**Product flag (fork worth confirming):** representing join semantics on the pipeline **graph**
(vs. leaving joins entirely to the Transform layer) is a genuine product decision. This ticket takes
the in-scope, declarative interpretation — the graph records the join *intent*, execution stays in
Transform. If the human prefers joins live only in Transform, park this ticket; the rest of the epic
(fields/mappings/transformations/validation) stands without it. Once decided, record it in the
Decision Log in `steering/00-project-overview.md`.

## Acceptance Criteria

- [ ] A Pydantic v2 join-specification model with: a **join type** (a closed set —
      inner/left/right/full — as a `StrEnum` or validated value) and an ordered collection of
      **key pairs**, each pairing a left-side field name with a right-side field name. Optional
      free-form `metadata` via a default factory. Fully type-annotated.
- [ ] A connection can carry an **optional** join spec (a plain edge with no join is unchanged and
      backward compatible with DANDER-2/4/5 graphs). The model makes clear which endpoint is the
      left vs. right side of the join, consistent with the edge's `from`/`to` direction, and this is
      documented.
- [ ] Intra-model constraints at the Pydantic boundary: the join type must be one of the accepted
      values (invalid value → clear validation error), and a join spec must declare at least one key
      pair. No cross-node field-existence checks here (that is DANDER-8).
- [ ] The join spec round-trips stably through **both** YAML and JSON via the existing load/dump
      functions: load → dump → load yields an equivalent graph (model equality), including a
      multi-key join and an edge with no join.
- [ ] Google-style docstrings on new/changed public models; fully type-annotated per
      `steering/languages/python.md`. No secrets or sample data anywhere.
- [ ] pytest tests cover: a connection loads a join spec (single- and multi-key) from YAML and JSON;
      the join type enum accepts valid values and rejects an invalid one; key pairs preserve order;
      the join spec round-trips stably in both formats; and a join-less edge is unchanged. Tests
      live under `tests/` and require no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the join-spec model + serialization + boundary
      constraints and their tests (no SQL generation, no execution, no cross-node validation).

## Design

### Approach

This is a pure model + serialization extension to the existing pipeline-graph in
`src/dander/pipeline/graph.py`. Everything lives in that one module and reuses the primitives
DANDER-2 established (`BaseModel`, `ConfigDict`, `Field`, alias handling, the existing
`load_*`/`dump_*` functions). No new module, no new dependency, no SQL, no execution — the graph
records join **intent**; the Transform layer will consume it later (`steering/00-project-overview.md`).

A connection that combines two sources is an existing `Edge`. We attach an **optional** join
specification to it: `Edge.join: JoinSpec | None`, defaulting to `None`. A join-less edge must
serialize byte-for-byte as it does today (backward compatible with DANDER-2/4/5 graphs), so the
`join` key is emitted only when present (see "Backward-compatible serialization" below).

**Left/right orientation (the endpoint question in AC-2):** the join's **left** side is the edge's
`from` node (`Edge.source`) and the **right** side is the edge's `to` node (`Edge.target`). Each key
pair therefore reads "a field on the `from`-node ↔ a field on the `to`-node". We deliberately use the
words *left*/*right* rather than *source*/*target* for the key-pair fields because on an `Edge` those
words already mean node **ids**, whereas here we mean field **names** on those nodes; keeping the
vocabularies distinct prevents that collision. This orientation is documented in the model
docstrings.

The join **type** is a closed set modelled as a `StrEnum`, matching the established convention in
`writer/base.py` (`WriteMode`) and `transform/model.py` (`Materialization`) — this gives clean
string values on disk, closed-set validation at the Pydantic boundary (an unknown value raises a
`ValidationError`), and equality/round-trip stability for free.

Field-existence checks (do these key fields actually exist on the joined nodes?) are explicitly **out
of scope** here — that is DANDER-8. This ticket enforces only intra-model constraints: valid join
type and at least one key pair.

### Interfaces / classes (all in `src/dander/pipeline/graph.py`)

- **`JoinType(StrEnum)`** — closed set of accepted join kinds:
  - `INNER = "inner"`, `LEFT = "left"`, `RIGHT = "right"`, `FULL = "full"`.
  - On-disk representation is the lowercase string value. An out-of-set value fails validation.

- **`JoinKeyPair(BaseModel)`** — one equality key pairing:
  - `left: str` — field name on the edge's **from** node (left side).
  - `right: str` — field name on the edge's **to** node (right side).
  - On-disk keys are `left`/`right` (documented, covered by tests). No metadata here — AC scopes
    optional metadata to the join spec as a whole. Referenced strictly **by field name**, never a
    value (`steering/01-security.md`).

- **`JoinSpec(BaseModel)`** — the declarative join on a connection:
  - `type: JoinType` — the join kind. On-disk key `type`, mirroring `Node.type`'s precedent of a
    plain `type` field (accepted house style even though it shadows the builtin at attribute level;
    keeps the on-disk vocabulary consistent with the rest of the graph). Invalid value → clear
    `ValidationError`.
  - `keys: list[JoinKeyPair] = Field(min_length=1, ...)` — ordered key pairs; **at least one**
    required (empty list → `ValidationError`). Ordering is preserved by the list and asserted in
    tests.
  - `metadata: dict[str, Any] = Field(default_factory=dict)` — optional free-form tags/labels only
    (never data/secrets), consistent with `Edge.metadata` / `Node.config`.
  - `model_config = ConfigDict(populate_by_name=True)` to match the sibling models.

- **`Edge`** (existing) gains one field:
  - `join: JoinSpec | None = Field(default=None)` — optional; `None` means a plain edge with no join.

### Backward-compatible serialization

A join-less edge must not gain a `join: null` key on disk. The cleanest fix that stays inside the
existing dump helpers is to add `exclude_none=True` to the four serializing calls in
`dump_graph_to_yaml` / `dump_graph_to_json` (and the JSON string path). This is safe because `None`
is only ever the value of the new optional `join` field — every other field defaults to a non-`None`
empty container (`{}`/`[]`) or is required, so `exclude_none` drops nothing else. Result: an edge
with no join dumps exactly as before; an edge with a join dumps the nested `join` block.
(Round-trip equality would hold even without this, since `join: null` reloads to `None`; we exclude
it to satisfy the "unchanged on disk" backward-compat criterion explicitly, and a test asserts a
join-less edge's dumped text contains no `join` key.)

Nested `JoinSpec`/`JoinKeyPair` need no alias gymnastics — their attribute names *are* their on-disk
keys — so the existing `by_alias=True` dumping continues to work unchanged for them.

### Files to touch

- **`src/dander/pipeline/graph.py`** — add `JoinType`, `JoinKeyPair`, `JoinSpec`; add the optional
  `join` field to `Edge`; add `exclude_none=True` to the dump helpers. Google-style docstrings on
  every new public model, documenting the left=`from` / right=`to` orientation.
- **`tests/pipeline/test_graph.py`** (or a new `tests/pipeline/test_graph_join.py` alongside it) —
  add the join-spec cases. Reuse the existing `tmp_path` + inline-doc pattern already in the file.

### Test seams

Pure models and file round-trip only — no network, no mocking (matches the existing graph tests).
Tests to add:
- An edge loads a **single-key** join from YAML and from JSON (type + one key pair).
- An edge loads a **multi-key** join from YAML and from JSON; assert key-pair **order** is preserved.
- `JoinType` accepts each valid value; an **invalid** join type raises `ValidationError`
  (use `pytest.raises`).
- An empty `keys` list raises `ValidationError` (the `min_length=1` boundary).
- Stable round-trip in **both** formats (load → dump → load → dump → load equality), including a
  join with `metadata`.
- A **join-less** edge is unchanged: it round-trips equal *and* its dumped text carries no `join`
  key (guards the `exclude_none` behavior).

### Trade-offs

- **`StrEnum` vs `Literal[...]` for the join type.** Chose `StrEnum` for parity with the two existing
  closed sets in the codebase (`WriteMode`, `Materialization`); it centralizes the accepted values,
  serializes to a plain string, and gives a clear boundary error. AC permits "`StrEnum` or validated
  value"; `StrEnum` is the house convention.
- **`left`/`right` vs `source`/`target` for key-pair fields.** Chose `left`/`right` to avoid
  overloading `Edge.source`/`Edge.target` (node ids) with a second meaning (field names). The
  from→left / to→right mapping is documented so the orientation is unambiguous.
- **Dedicated `JoinKeyPair` model vs a `(str, str)` tuple or `dict`.** A model gives a named,
  validated, self-documenting on-disk shape and a natural seam for DANDER-8's per-key validation,
  at trivial cost.
- **Optional join via `None` + `exclude_none` vs a sentinel/empty object.** `None` is the idiomatic
  "absent" and, paired with `exclude_none` on dump, preserves the exact legacy on-disk form for
  plain edges — the strongest backward-compat guarantee.
- **`metadata` on `JoinSpec` only (not on `JoinKeyPair`).** AC scopes optional metadata to the join
  spec; keeping key pairs minimal avoids speculative fields (`steering/02-engineering.md`: don't
  build what no ticket asks for).

### Notes / flags

- **Product fork (from Context) is unresolved.** Representing join semantics on the graph vs.
  leaving joins entirely to Transform is a real product decision. This design implements the
  in-scope, declarative interpretation the ticket selected; if the human parks joins in Transform,
  this ticket is dropped. Either way the outcome should be recorded in the Decision Log in
  `steering/00-project-overview.md` (the Code agent should not invent that decision — surface it).
- **Cross-ticket ordering.** DANDER-5 (`FieldMapping` on `Edge`) is `in-code` and also edits `Edge`
  in the same module. If DANDER-5's `mappings` field is already present when this lands, add `join`
  alongside it; if not, this change is independent and non-conflicting. No behavioral coupling
  between `mappings` and `join`.
- **AC "makes clear which endpoint is left vs right" is satisfied by documentation + field naming**,
  not by a runtime check — consistent with the "model + serialization only, validation is DANDER-8"
  scope. Called out here so PR-Review reads it as intentional, not an omission.

## Implementation Notes

Implemented exactly per Design, entirely in `src/dander/pipeline/graph.py`:

- Added `JoinType(StrEnum)` with `INNER`/`LEFT`/`RIGHT`/`FULL` members (lowercase string values),
  matching the `WriteMode`/`Materialization` convention.
- Added `JoinKeyPair(BaseModel)` with `left`/`right` `str` fields (on-disk keys `left`/`right`,
  `populate_by_name=True`).
- Added `JoinSpec(BaseModel)` with `type: JoinType`, `keys: list[JoinKeyPair] = Field(min_length=1)`,
  `metadata: dict[str, Any] = Field(default_factory=dict)`, `populate_by_name=True`. Docstrings
  document the left=`from`/right=`to` orientation as specified.
- Added `Edge.join: JoinSpec | None = Field(default=None)` — optional, defaults to `None`.
- Added `exclude_none=True` to both graph-level dump calls (`dump_graph_to_yaml`'s
  `model_dump(..., exclude_none=True)` and `dump_graph_to_json`'s `model_dump_json(...,
  exclude_none=True)`) so a join-less edge emits no `join` key on disk. There were only these two
  serializing call sites in the module (the Design's "four serializing calls" note did not match
  what's actually in `graph.py` today — no separate "JSON string path" function exists); both are
  covered.
- No new module, no SQL, no execution, no cross-node validation (DANDER-8 territory) — scope held
  exactly as specified.

**Deviation (test-only, required for correctness, not a design change):** two **existing**
`test_graph.py` tests (`test_edge_dump_emits_reserved_keyword_keys_not_attribute_names`,
`test_edge_with_no_mappings_is_unchanged_from_prior_shape`) call `Edge.model_dump(by_alias=True)`
**directly** (not through `dump_graph_to_yaml`/`dump_graph_to_json`), so the new
`exclude_none=True` on the graph-level dump helpers does not reach them — adding the `join` field
makes their expected dicts naturally gain a `"join": None` entry (Pydantic dumps every field by
default). Updated both expected dicts to include `"join": None`. This does not weaken the
backward-compatibility guarantee: that guarantee is about on-disk file output via
`dump_graph_to_yaml`/`dump_graph_to_json` (per Design), which is covered by dedicated new tests
(`test_join_less_edge_round_trips_unchanged_and_omits_join_key`) asserting the literal string
`"join"` is absent from the dumped YAML/JSON text.

New test file `tests/pipeline/test_graph_join.py` (alongside `test_graph.py`, per Design's stated
option) covers every case in the AC/Test-seams list: single- and multi-key join load from YAML and
JSON; multi-key order preservation; each valid `JoinType` value accepted and an invalid one
rejected (`ValidationError`); empty `keys` rejected (`min_length=1` boundary); stable round-trip in
both formats including a join with `metadata`; a join-less edge round-trips equal and its dumped
text has no `join` key; an edge with a join dumps a nested `join` block with `type`/`keys` in both
formats.

**Tooling:** `uv run ruff check`, `uv run ruff format --check`, and `uv run mypy` are clean on
`src/dander/pipeline/graph.py` and the touched/new test files; `uv run pytest` is green across
`tests/pipeline/` (all tests) and the full suite (82 passed). Note: `uv run ruff check` on the
**whole repo** reports one pre-existing `E501` in `scripts/watch_workflows.py`, unrelated to this
ticket and unmodified by it (confirmed via `git stash`: present on `main` before this change) —
outside this ticket's scope to fix.

**Unresolved product fork (surfaced, not decided by this agent):** per the ticket's Context/Notes,
whether join semantics belong on the pipeline graph at all (vs. living only in Transform) is a
real product decision that has not been recorded in the Decision Log
(`steering/00-project-overview.md`). This implementation takes the in-scope, declarative
interpretation the ticket selected; the human should confirm and log the decision.

### Addendum fix (2026-07-22)

Addressed all three blocking items from the 2026-07-22 FAIL review. The prior graph-wide
`exclude_none=True` on the two dump helpers has been fully removed and replaced with a scoped
omission of only `Edge.join` when it is `None`:

1. **`src/dander/pipeline/graph.py` — scoped the `join`-only omission.** Rather than a
   `@model_serializer(mode="wrap")` on `Edge` (the addendum's first suggested mechanism), a
   `model_serializer` proved too broad in practice: it changes `Edge.model_dump()` for *every*
   caller, not just the graph-level dump helpers, which would have broken the two pre-existing
   `test_graph.py` tests that assert `edge.model_dump(by_alias=True)` includes a literal
   `"join": None` (`test_edge_dump_emits_reserved_keyword_keys_not_attribute_names`,
   `test_edge_with_no_mappings_is_unchanged_from_prior_shape`). Instead took the addendum's
   second suggested mechanism: a new private helper `_dump_graph_payload(graph)` that calls
   `graph.model_dump(by_alias=True, mode="json")` (no `exclude_none`) and then, only for edges
   whose `Edge.join is None`, pops that one edge's `"join"` key from the already-built payload
   dict. `dump_graph_to_yaml` and `dump_graph_to_json` both now call this shared helper instead
   of dumping directly; `dump_graph_to_json` switched from `model_dump_json(...)` to
   `json.dumps(_dump_graph_payload(graph), indent=indent)` so both formats share one payload
   builder and one omission rule. Every other field — including other meaningful `None`s such as
   `Transformation.constant`, `FieldMapping.source`, `FieldMapping.transformation` — is left
   completely untouched by this helper. Verified the addendum's exact repro (a `CONSTANT`
   transformation with `constant=None`) now round-trips through both
   `dump_graph_to_yaml`/`load_graph_from_yaml` and `dump_graph_to_json`/`load_graph_from_json`
   without raising.
2. **Added the regression test.** `tests/pipeline/test_transformations.py` gained
   `test_constant_null_round_trips_through_dump_graph_to_yaml` and
   `test_constant_null_round_trips_through_dump_graph_to_json` (plus a shared
   `_graph_with_null_constant()` builder), each constructing the addendum's repro graph
   (`FieldMapping(target="flag", transformation=Transformation(kind=CONSTANT, constant=None))`),
   dumping it through the respective helper, reloading, and asserting model equality. Placed in
   `test_transformations.py` (not `test_graph_join.py`) since the regression is about
   `Transformation`/dump-helper interaction, not the join spec itself; the ticket's addendum
   named either location as acceptable.
3. **Re-verified the join-less backward-compat guarantee.**
   `test_join_less_edge_round_trips_unchanged_and_omits_join_key` in
   `tests/pipeline/test_graph_join.py` required no changes and still passes unmodified under the
   scoped fix — a join-less edge's dumped YAML/JSON text still contains no `"join"` key.

**Tooling (re-verified after the fix):** `uv run ruff check`, `uv run ruff format --check`, and
`uv run mypy` are clean on `src/dander/pipeline/graph.py` and
`tests/pipeline/test_transformations.py`; `uv run pytest` is green across `tests/pipeline/` and
the full suite. Whole-repo `uv run ruff check .` still reports only the same single pre-existing,
unrelated `E501` in `scripts/watch_workflows.py` noted before (confirmed unmodified by this
change) — outside this ticket's scope.

**Unresolved product fork — still open, unchanged by this addendum:** the Decision Log entry in
`steering/00-project-overview.md` for join-on-graph vs. Transform-only remains for the human to
record; this addendum did not touch it (non-blocking per the review).

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-22 — FAIL (pr-review)

The join-spec model itself is correct, well-documented, and well-tested — `JoinType`/`JoinKeyPair`/
`JoinSpec` and the optional `Edge.join` field meet AC-1/2/3/5, and `ruff check`, `ruff format
--check`, and `mypy` are clean. But the ticket's serialization change introduces a **blocking
round-trip regression** in a sibling model, so AC-4 ("round-trips stably … via the existing
load/dump functions") and AC-7 ("suite remains green") are not truly satisfied across the graph.

**Addendum (concrete, numbered):**

1. **`src/dander/pipeline/graph.py` — `dump_graph_to_yaml` (line 383) and `dump_graph_to_json`
   (line 398): the graph-wide `exclude_none=True` breaks round-trip for a `CONSTANT` transformation
   with an explicit null constant.** The Design justified `exclude_none=True` on the claim that
   "`None` is only ever the value of the new optional `join` field." That claim is false now that
   DANDER-5/6 have landed: `FieldMapping.source`, `FieldMapping.transformation`, and
   `Transformation.constant` are all nullable. For `Transformation.constant`, `None` is a
   **meaningful** value — DANDER-6 (status `done`) supports an authored `constant: null` and
   distinguishes it via `model_fields_set` (`test_constant_kind_accepts_explicit_null_literal`).
   `exclude_none=True` silently drops that `constant: null` key on dump; on reload the
   `CONSTANT`-kind validator then raises
   `ValidationError: Transformation(kind=constant) requires a 'constant' literal to be set`.

   Reproduce (both formats fail identically):
   ```python
   g = PipelineGraph(
       name="g",
       nodes=[Node(id="n1", type="source", name="a"), Node(id="n2", type="target", name="b")],
       edges=[Edge(source="n1", target="n2", mappings=[
           FieldMapping(target="flag",
                        transformation=Transformation(kind=TransformationKind.CONSTANT,
                                                       constant=None))])],
   )
   dump_graph_to_yaml(g, p); load_graph_from_yaml(p)   # -> ValidationError
   dump_graph_to_json(g, q); load_graph_from_json(q)   # -> ValidationError
   ```
   **Fix:** omit only the `Edge.join` key when it is `None`, never all `None` values graph-wide.
   Drop the two `exclude_none=True` args and instead scope the omission to `join` — e.g. a
   `@model_serializer(mode="wrap")` on `Edge` that pops `join` when `None`, or prune only
   `edge.join is None` from the dumped payload. This must leave `Transformation.constant`,
   `FieldMapping.source`, and `FieldMapping.transformation` untouched on disk.

2. **Add a regression test that would have caught this.** In `tests/pipeline/test_graph_join.py`
   (or `test_transformations.py`), dump-and-reload a graph containing a `CONSTANT` transformation
   with `constant=None` through **both** `dump_graph_to_yaml` and `dump_graph_to_json`, asserting
   model equality after reload. The existing round-trip tests only construct a constant-null
   in-memory; none pushes one through the dump helpers, which is why the suite stayed green while
   the on-disk path was broken.

3. **Re-verify the join-less backward-compat guarantee still holds under the scoped fix.** Keep the
   `test_join_less_edge_round_trips_unchanged_and_omits_join_key` assertions (no `join` key on
   disk) passing with whatever mechanism replaces `exclude_none`.

Everything else in the ticket (model shape, orientation docs, enum/min_length boundary constraints,
join load/round-trip tests, no secrets/PII, no scope creep) is acceptable — only the shared-dump
regression above blocks. Also, as the Implementation Notes correctly surface, the unresolved product
fork (join semantics on the graph vs. Transform-only) still needs a Decision Log entry by the human;
that is not a code blocker.

### 2026-07-22 — PASS (pr-review)

The addendum fix resolves the blocking regression cleanly and every acceptance criterion is now met
and verified against the actual code.

- **Blocking item 1 (fixed) — scoped omission.** The graph-wide `exclude_none=True` is gone. A new
  private `_dump_graph_payload` (graph.py:374) does `graph.model_dump(by_alias=True, mode="json")`
  with no `exclude_none`, then pops only the `join` key of edges whose `Edge.join is None` (via
  `zip(..., strict=True)` over `graph.edges` and the dumped payload). Both `dump_graph_to_yaml` and
  `dump_graph_to_json` route through it; JSON switched to `json.dumps(_dump_graph_payload(...))`.
  Every other `None` — including `Transformation.constant`, `FieldMapping.source`,
  `FieldMapping.transformation` — is untouched. I ran the FAIL's exact repro (a `CONSTANT`
  transformation with `constant=None`): it now round-trips through both YAML and JSON without
  raising, and the dumped YAML preserves `constant: null`.
- **Blocking item 2 (fixed) — regression test added.** `test_transformations.py` gained
  `_graph_with_null_constant()` plus `test_constant_null_round_trips_through_dump_graph_to_yaml`
  and `..._to_json`, each dumping-through-the-helpers and asserting model equality on reload —
  exactly the on-disk path the prior suite never exercised.
- **Blocking item 3 (verified) — join-less backward-compat holds.**
  `test_join_less_edge_round_trips_unchanged_and_omits_join_key` still passes under the scoped fix:
  a join-less edge's dumped YAML/JSON contains no `join` key and reloads equal. The two pre-existing
  `test_graph.py` tests that call `edge.model_dump(by_alias=True)` directly correctly expect
  `"join": None` (the fix deliberately does not use a `model_serializer`, so direct `model_dump`
  is unchanged) — a sound choice that keeps those assertions honest.

AC coverage: AC-1/2/3/5 (model shape, optional `Edge.join`, left=`from`/right=`to` orientation
documented, closed enum + `min_length=1` boundary, Google-style docstrings, full typing) were
already good and remain so; AC-4 (stable YAML+JSON round-trip incl. multi-key and join-less) and
AC-7 (suite green) are now genuinely satisfied across the whole graph. `uv run ruff check`,
`ruff format --check`, and `mypy` are clean on the touched files; `uv run pytest` is green
(81 passed). Security: no credential literals in the diff (grep hits are steering-compliant
docstring references only); no PII/sample data. Scope held — model + serialization + boundary
constraints only, no SQL/execution/cross-node validation.

Non-blocking (carried, not a code gate): the product fork — join semantics on the pipeline graph
vs. Transform-only — still needs a Decision Log entry in `steering/00-project-overview.md` by the
human; the Implementation Notes correctly surface it rather than inventing the decision. The single
pre-existing `E501` in `scripts/watch_workflows.py` is unrelated to and unmodified by this ticket.

Verdict: **PASS.** Status → `done`.
