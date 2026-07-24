---
id: DANDER-19
title: Visual/layout metadata on Node
status: done
component: python
epic: pipeline-config
depends_on: []
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (see DANDER-10 for the shared
review context).

The module docstring at the top of `src/dander/pipeline/graph.py` already states that nodes are meant
to back "a future drag-drop UI," but `Node` today has no position / color / icon fields — a visual
editor cannot persist where a node sits or how it looks. This is **low priority** relative to the
other gap tickets and must not block any of them.

This ticket adds optional **visual/layout metadata** to `Node` (e.g. x/y position, color, icon) so a
future UI can round-trip layout. It is purely additive, presentation-only metadata; it changes no
execution or data semantics.

## Acceptance Criteria

- [ ] `Node` gains optional visual/layout metadata sufficient for a drag-drop UI: at least a position
      (x/y) and presentation hints (e.g. color, icon). Fully type-annotated, all optional.
- [ ] The metadata is presentation-only and does not affect any data/execution semantics; it is a
      separate, clearly-named concern (not overloaded onto the existing free-form `config`/`metadata`
      that carries data-shaping intent).
- [ ] Backward compatibility: a `Node` without any visual metadata loads and round-trips exactly as
      before (all fields optional / defaulted via factory, no mutable default args).
- [ ] Visual metadata round-trips stably through YAML and JSON via the existing load/dump functions
      (load → dump → load model equality).
- [ ] Google-style docstrings noting this is presentation metadata for the future UI referenced in
      the `graph.py` module docstring; typed per `steering/languages/python.md`. No secrets in
      fixtures.
- [ ] pytest tests cover: a node loads visual metadata from YAML and JSON; round-trip stability; and
      a node without visual metadata is unchanged. Tests live under `tests/`, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the visual-metadata fields + serialization + tests. No
      UI, no rendering logic.

## Design

### Approach

This is a purely additive, presentation-only change to the declarative model in
`src/dander/pipeline/graph.py`. We introduce a single, clearly-named `visual` concern on `Node`
that a future drag-drop UI can round-trip, kept strictly separate from the existing `config`
(data-shaping intent) and any `metadata` (tags/labels). Nothing about execution or data semantics
changes; no code reads `visual` to make decisions — it is inert layout state, exactly like `join`
and `mappings` are inert intent for the Transform layer.

Rather than sprinkle loose `x`/`y`/`color`/`icon` fields directly onto `Node` (which would blur the
presentation concern into the node's core identity and grow its attribute surface), we model the
concern as its own small Pydantic v2 model, `NodeVisual`, attached via one optional field
`Node.visual: NodeVisual | None = None`. Coordinates are grouped into a nested `Position(x, y)` so
"where the node sits" is one cohesive value, and a UI can persist a color/icon without a position
(or vice versa). This mirrors the established shape in this module: closed/opaque sub-models
(`JoinSpec`, `Transformation`, `NodeField`) composed onto the primary models, presentation kept out
of the free-form dicts.

**Serialization.** `visual` defaults to `None`, so it is immutable — no `default_factory`, no
mutable default arg. For true backward compatibility we must not let a node that has no visual
metadata sprout a `visual: null` key on dump (older graphs would no longer round-trip byte-for-byte,
and a fresh fieldless node's on-disk form would change). We reuse the exact precedent already set for
join-less edges in `_dump_graph_payload`: after `model_dump`, walk the nodes and `pop("visual")` from
any dumped node whose `Node.visual is None`. Scoping the omission there (not a blunt graph-wide
`exclude_none=True`) preserves every other meaningful `None` in the graph — notably an authored
`constant: null` on a `CONSTANT` `Transformation`. A node *with* visual metadata is new on-disk
content, so inner `None`s within a present `NodeVisual` (e.g. `position: null` when only a color is
set) are left as-is; they round-trip to `None` and model equality holds. Load functions need no
change — Pydantic validates the nested `visual` block automatically.

**Backward compatibility & round-trip.** A `Node` constructed or loaded without `visual` yields
`visual is None` and dumps identically to a DANDER-2/4/5/6 node (the `visual` key is absent).
`load → dump → load` model equality holds for nodes with and without visual metadata, across both
YAML and JSON, because model equality already drives the existing round-trip tests and the dump
helper only removes a key that reloads to the same `None`.

### Interfaces / classes

- **`Position(BaseModel)`** — a 2-D canvas coordinate for a node.
  - Fields: `x: float`, `y: float` (both required *within* a `Position`; `float` covers integer and
    fractional canvas coordinates). Declaring a position means giving both coordinates.
  - Responsibility: cohesive value object for "where the node sits". Opaque units (UI canvas space);
    no validation of ranges — that is a UI concern, out of scope.

- **`NodeVisual(BaseModel)`** — presentation/layout hints for one node, all optional.
  - Fields: `position: Position | None = None`, `color: str | None = None`, `icon: str | None = None`.
  - `color` is a free-form string (e.g. a hex code or token); `icon` is a free-form string (an icon
    name/reference). Validation of accepted color/icon formats is deferred — not this ticket's scope.
  - Responsibility: the single, clearly-named presentation concern. Carries no data values and no
    execution semantics; never a place for secrets/PII (`steering/01-security.md`).

- **`Node`** — gains one field: `visual: NodeVisual | None = Field(default=None)`. Immutable default,
  so no mutable-default hazard; `populate_by_name` on `Node` is unaffected. Docstring gains a
  `visual` entry noting it is presentation-only metadata for the future drag-drop UI named in the
  module docstring, explicitly *not* overloaded onto `config`.

- **`_dump_graph_payload`** — extended to also strip a node's `visual` key when `node.visual is None`,
  in the same post-dump pass that already strips join-less `join` keys. Its docstring is updated to
  state both omissions and why the scoping is deliberate.

`Position` and `NodeVisual` are defined just above `Node` (dependency order), matching how
`NodeField` precedes `Node` today.

### Files to touch / create

- **`src/dander/pipeline/graph.py`** (edit): add `Position` and `NodeVisual` models; add the
  `visual` field to `Node` with a Google-style docstring entry; extend `_dump_graph_payload` (and its
  docstring, plus the `dump_graph_to_yaml`/`dump_graph_to_json` docstrings if they enumerate
  omissions) to drop the `visual` key for visual-less nodes.
- **`tests/pipeline/test_graph_visual.py`** (create): pytest unit tests, no network, `tmp_path` for
  file round-trips, synthetic non-sensitive fixtures only.

### Trade-offs

- **Nested `NodeVisual`/`Position` vs. flat `x`/`y`/`color`/`icon` on `Node`.** Chosen: nested. It
  isolates the presentation concern behind one clearly-named field (satisfies the "separate,
  clearly-named concern" criterion cleanly), keeps `Node`'s core attribute surface small (SRP), and
  matches the module's composition-of-small-models idiom. Cost: one extra level of nesting on disk —
  acceptable and idiomatic here.
- **`position` as a required-pair sub-model vs. independent optional `x`/`y`.** Chosen: a `Position`
  with both coords required when present. A half-specified coordinate (`x` but no `y`) is meaningless
  for placement; requiring both when a position exists is the honest contract, while `position` itself
  stays optional so color/icon-only visuals are allowed.
- **Stripping `visual: null` on dump vs. accepting the null key.** Chosen: strip, reusing the
  `_dump_graph_payload` precedent. Model-equality round-trip would pass either way, but "round-trips
  exactly as before" and this codebase's established join handling both call for on-disk fidelity, so
  a visual-less node's serialized form is unchanged.
- **`float` vs. `int` for coordinates.** Chosen: `float` — supersets integer input and supports
  fractional canvas positions a UI may emit; Pydantic coerces integer literals to float.

### Test seams

Pure models + pure serialization functions — no network, no external clients, nothing to mock.
Add `tests/pipeline/test_graph_visual.py` covering:
- A node loads `visual` (position + color + icon) from **YAML**; asserts nested values.
- A node loads `visual` from **JSON**; asserts nested values.
- Round-trip stability with visual metadata: `load → dump → load` model equality, for both YAML and
  JSON, including a node that sets only some `NodeVisual` fields (e.g. color/icon, no position, or
  position-only) to exercise inner-`None` round-tripping.
- A node **without** visual metadata is unchanged: `visual is None`, and the dumped payload contains
  no `visual` key (assert on the on-disk text/parsed dict), and it still round-trips equal.
- Constructed-in-Python graph mixing a visual and a visual-less node round-trips equal via both
  formats (mirrors `test_graph_fields.py`'s mixed-node test).

Fixtures use synthetic tokens only (e.g. `color: "#3366cc"`, `icon: "database"`, integer/float
coordinates) — never real field values or sample data (`steering/01-security.md`).

### Notes / flagged ambiguities

- The ticket says "e.g. color, icon" — the design commits to exactly `position` + `color` + `icon`
  and nothing more, to stay inside scope (no width/height/z-index/rotation speculation). Adding more
  presentation hints later is a non-breaking additive change.
- `color`/`icon` are intentionally free-form strings; enforcing a hex/enum format is a UI-facing
  validation concern and is explicitly out of scope here (consistent with how `Node.type` and
  `NodeField.type` defer value validation).

## Implementation Notes

Implemented exactly per the Design section, no deviations.

- **`src/dander/pipeline/graph.py`**:
  - Added `Position(BaseModel)` (`x: float`, `y: float`, both required) and
    `NodeVisual(BaseModel)` (`position: Position | None`, `color: str | None`, `icon: str | None`,
    all optional/`None`-defaulted), defined immediately above `Node`, matching the module's
    existing dependency-order convention (`NodeField` before `Node`).
  - Added `Node.visual: NodeVisual | None = Field(default=None)` with a new `Attributes` entry in
    `Node`'s docstring calling out that it is presentation-only metadata for the future drag-drop
    UI (DANDER-19), kept separate from `config`.
  - Extended `_dump_graph_payload` to pop a node's `visual` key when `node.visual is None`, in the
    same post-dump pass that already strips join-less `join`, spec-less `request`, writer-less
    `writer`, trigger-less `trigger`, and cursor-less `cursor`. Updated its docstring and the
    `dump_graph_to_yaml`/`dump_graph_to_json` docstrings to enumerate the new omission.
  - No changes to `load_graph_from_yaml`/`load_graph_from_json` — Pydantic validates the nested
    `visual` block automatically, no code path reads `visual` to make any decision.

- **`tests/pipeline/test_graph_visual.py`** (new): pytest, no network, `tmp_path` for all file
  I/O, synthetic-only fixtures (`color: "#3366cc"`, `icon: "database"`/`"table"`, plain numeric
  coordinates). Covers: loading `visual` (position + color + icon) from YAML and from JSON;
  YAML and JSON round-trip stability (`load -> dump -> load` equality, twice, mirroring the
  cursor/trigger test pattern); a `NodeVisual` with only `color`/`icon` (no `position`) round-trips
  equal in both formats; a `NodeVisual` with only `position` (no `color`/`icon`) round-trips equal
  in both formats; a visual-less node dumps with no `visual` key at all (asserted on raw on-disk
  text) and round-trips equal, in both formats; a node with visual metadata dumps a nested
  `visual:`/`"visual"` block with the expected inner values, in both formats; and a graph mixing a
  visual and a visual-less node round-trips equal (mirrors `test_graph_fields.py`'s mixed-node
  test).

**Tooling (repo-wide):**
- `uv run ruff check .` — clean except one pre-existing, unrelated `E501` in
  `scripts/watch_workflows.py` (not touched by this ticket; present before this change).
- `uv run ruff format --check` — clean for all files touched by this ticket (reformatted the new
  test file once to match Ruff's formatting, then verified clean).
- `uv run mypy src` — `Success: no issues found in 28 source files`.
- `uv run pytest` — full suite green (233 tests in `tests/pipeline/` including the 10 new visual
  tests; project-wide suite also green).

No scope beyond the visual-metadata fields, their serialization, and tests — no UI, no rendering
logic, no new validation of color/icon formats (deferred per Design/Notes).

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed the implementation in `src/dander/pipeline/graph.py` and the new
`tests/pipeline/test_graph_visual.py` against all acceptance criteria and the steering files.

**Acceptance criteria — all met:**
- `Node.visual: NodeVisual | None = Field(default=None)` adds optional presentation/layout
  metadata: `NodeVisual(position: Position | None, color: str | None, icon: str | None)` with
  `Position(x: float, y: float)`. Fully type-annotated, all optional (except x/y being a
  required pair *within* a declared `Position`, which is the honest contract per Design).
- Presentation-only and inert: nothing reads `visual` to make a decision; it is a separate,
  clearly-named concern, not overloaded onto `config`.
- Backward compatible: immutable `Field(default=None)` (no mutable default arg); a visual-less
  node loads/dumps exactly as before — `_dump_graph_payload` pops the `visual` key when
  `node.visual is None`, reusing the established join/request/writer/trigger/cursor precedent, so
  no `visual: null` key appears on disk. Verified by
  `test_visual_less_node_round_trips_unchanged_and_omits_visual_key` asserting on raw text.
- Round-trips stably through YAML and JSON (`load → dump → load` model equality), including
  partially-populated `NodeVisual` (color/icon-only and position-only) exercising inner-`None`
  round-tripping.
- Google-style docstrings on `Position`, `NodeVisual`, and the new `Node.visual` attribute,
  noting presentation-only intent and the future drag-drop UI in the module docstring; typed per
  `steering/languages/python.md`. `_dump_graph_payload` / dump-helper docstrings updated to
  enumerate the new omission.
- pytest coverage present under `tests/`, no network, `tmp_path` for I/O: loads from YAML and
  JSON, round-trip stability (both formats), visual-less node unchanged, partial-visual variants,
  nested-block dump assertion, and a mixed visual/visual-less graph round-trip.

**Tooling (verified in this review):** `uv run ruff check` and `ruff format --check` clean on
touched files; `uv run mypy src` — success, 28 files; `uv run pytest` — 275 passed (the single
warning is a pre-existing, unrelated `TestKind` collection warning).

**Security:** no hardcoded secrets/PII; fixtures use synthetic tokens only (`#3366cc`,
`database`/`table`, plain coordinates); credential-shaped grep hits are docstring references to
steering, not literals. `.env.example` needs no change (no new secret keys).

**Design fidelity / scope:** matches the approved Design exactly (nested `NodeVisual`/`Position`,
scoped dump omission); no scope creep — no UI, rendering, or color/icon format validation.

No blocking issues.
