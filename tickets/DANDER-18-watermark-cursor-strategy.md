---
id: DANDER-18
title: Surface a watermark/cursor strategy at the node/graph level
status: done
component: python
epic: pipeline-config
depends_on: []
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (see DANDER-10 for the shared
review context).

The control-table / idempotency design in `steering/00-project-overview.md` and
`steering/02-engineering.md` needs a per-source+entity **watermark/cursor**. Today only
`Endpoint.incremental_cursor` exists in `src/dander/ingestion/source.py` — just a field name, with no
cursor kind (timestamp / sequence / opaque token) or bounds, and it is disconnected from the pipeline
graph model.

This ticket models a proper **watermark/cursor strategy** and surfaces it at the node/graph level so
a `source`/ingestion node can declare how it resumes incrementally: the cursor field plus its kind
(e.g. timestamp / monotonic sequence / opaque token). Model + serialization + validation only — no
control table is read/written and no state is persisted here (that remains Orchestration/State work).

## Acceptance Criteria

- [ ] A declarative watermark/cursor strategy model: the cursor field name plus a cursor kind (a
      named closed set, e.g. timestamp / sequence / opaque token) and any params that kind needs.
      Fully type-annotated.
- [ ] The strategy is surfaced at the node/graph level (attachable to the relevant source/ingestion
      node config or graph model) rather than living only on the ingestion `Endpoint`, and either
      supersedes or cleanly maps the existing `Endpoint.incremental_cursor` (document the migration;
      keep existing connector YAML loadable).
- [ ] Boundary constraints are enforced (e.g. a cursor kind requires a non-empty cursor field),
      raising a clear validation error. No state is read, written, or persisted here.
- [ ] Backward compatibility: a node/endpoint with no incremental cursor still loads and
      round-trips; the strategy is optional.
- [ ] The cursor strategy round-trips stably through YAML and JSON via the existing load/dump
      functions (load → dump → load model equality).
- [ ] Google-style docstrings referencing the control-table/idempotency design in
      `steering/00-project-overview.md` and `steering/02-engineering.md`, noting state persistence is
      out of scope here; typed per `steering/languages/python.md`. No secrets in fixtures.
- [ ] pytest tests cover: a node/endpoint loads a cursor strategy for each kind from YAML and JSON;
      boundary constraints reject a malformed strategy; round-trip stability; and a cursor-less node is
      unchanged. Tests live under `tests/`, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the cursor-strategy model + validation + serialization
      + tests. No control-table persistence, no state I/O.

## Design

### Approach

This is a **model + serialization + validation** ticket in the exact mold of the DANDER-6
`Transformation` and DANDER-7 `JoinSpec`/`Edge.join` work already merged in
`src/dander/pipeline/graph.py`. Nothing here reads, writes, or persists state — that stays in
Orchestration/State (the `WatermarkStore` ABC in `src/dander/state/watermark.py` is the persistence
seam; this ticket only declares the *strategy* a store would later honor). We reuse the package's
established conventions rather than invent new ones: a closed `StrEnum` for the kind, a Pydantic v2
value model, an `after` `model_validator` for the boundary constraint, an optional `None`-defaulted
attribute on the graph model, and a scoped omit-when-`None` rule in `_dump_graph_payload` so
existing graphs round-trip byte-identically.

**Where it attaches.** The strategy is surfaced at the **node** level by adding an optional
`cursor: CursorStrategy | None = None` attribute to `Node` — the direct analogue of
`Edge.join: JoinSpec | None`. This is the "node/graph level" the ticket asks for and supersedes the
narrow `Endpoint.incremental_cursor` string (which was just a field name, disconnected from the
graph). A source/ingestion node declares *how* it resumes; the model does not enforce that
`node.type == "source"` (accepted-value validation of `Node.type` is deliberately deferred across
this whole package — same treatment as `JoinSpec` on any edge). Putting it on a typed `Node.cursor`
field — rather than burying it in the free-form `Node.config` dict — keeps it type-annotated,
validated at the boundary, and discoverable, consistent with how `fields`/`join`/`mappings` were
added.

**Migration of `Endpoint.incremental_cursor`.** We **keep** `Endpoint.incremental_cursor` on the
ingestion model so existing connector YAML keeps loading unchanged (backward-compat AC), but
document it as the legacy, narrow form that the node-level `CursorStrategy` supersedes. To make the
mapping *clean* rather than implicit, add a pure classmethod
`CursorStrategy.from_incremental_cursor(cursor_field: str | None) -> CursorStrategy | None` that
returns `None` for `None`/empty and otherwise a `CursorStrategy(field=cursor_field,
kind=CursorKind.TIMESTAMP)` — TIMESTAMP because the historical `extract(..., since=...)` contract in
`source.py` treats the cursor as a monotonic "since" bound, which is timestamp-shaped by default.
The classmethod takes a plain string, so `pipeline` gains **no** import dependency on `ingestion`;
the ingestion/orchestration layer calls it when it wants a strategy from a legacy endpoint. The
TIMESTAMP default is a documented assumption (see Notes/flags) — a connector whose legacy cursor was
a sequence/token must author an explicit node-level `CursorStrategy`.

**Serialization & backward compat.** `CursorStrategy` serializes as a nested block under the `cursor`
key on a node, exactly like `join` on an edge. A cursor-less node must dump **without** a `cursor`
key (not `cursor: null`) so pre-DANDER-18 graphs round-trip identically; this is done by extending
`_dump_graph_payload` with a second loop that pops the `cursor` key from each dumped node whose
`Node.cursor is None`, mirroring the existing per-edge `join` pop. We reuse that scoped-pop approach
rather than a blunt `exclude_none=True` for the same reason documented in `_dump_graph_payload`: a
global drop would also delete meaningful `None`s elsewhere (e.g. an authored `constant: null`).

### Interfaces / classes (all in `src/dander/pipeline/graph.py`)

- **`CursorKind(StrEnum)`** — the closed set of cursor kinds, mirroring `JoinType`/`TransformationKind`:
  - `TIMESTAMP = "timestamp"` — a time-ordered cursor (e.g. an updated-at). The default for a mapped
    legacy `incremental_cursor`.
  - `SEQUENCE = "sequence"` — a monotonically increasing numeric/sequence id.
  - `OPAQUE_TOKEN = "opaque_token"` — a source-supplied continuation token treated as opaque (never
    parsed or ordered here).
  A `StrEnum` (not a bare `Literal`) so downstream layers branch on a named importable type while it
  serializes to/from its plain string value; an out-of-set value fails Pydantic validation with a
  clear error.

- **`CursorStrategy(BaseModel)`** — the declarative watermark/cursor strategy. `model_config =
  ConfigDict(populate_by_name=True)`. Attributes:
  - `field: str` — the cursor field name the source advances on. Referenced **by name only**, never
    a value (`steering/01-security.md`).
  - `kind: CursorKind` — the discriminator (required; no default, since a cursor with no declared
    kind is meaningless — unlike `Transformation.kind` which defaults to `DIRECT`).
  - `params: dict[str, Any] = Field(default_factory=dict)` — free-form, kind-specific parameters
    (e.g. a timestamp format hint), matching the `metadata`/`config` precedent. Opaque and inert:
    stored as-authored for the State/Orchestration layer, never interpreted here, and (per
    `steering/01-security.md`) never a place for a secret/credential — names/params only.
  - `metadata: dict[str, Any] = Field(default_factory=dict)` — free-form tags/labels only, matching
    `JoinSpec.metadata`.
  - **`@model_validator(mode="after") _check_field_present`** — the boundary constraint: raises
    `ValueError` (surfaced as Pydantic `ValidationError`) when `field` is empty or whitespace-only
    (`not self.field.strip()`), with a clear message. Uses `.strip()` for whitespace-robustness,
    matching the `EXPRESSION` check in `Transformation`. (A bare `Field(min_length=1)` would miss
    `"   "`, so the validator is the deliberate choice.)
  - **`@classmethod from_incremental_cursor(cls, cursor_field: str | None) -> CursorStrategy | None`**
    — the documented migration bridge described above.

- **`Node`** — add `cursor: CursorStrategy | None = Field(default=None)`. Docstring gains a `cursor`
  attribute note: optional; `None` (default) means the node declares no incremental cursor and
  round-trips exactly as a pre-DANDER-18 node; supersedes `Endpoint.incremental_cursor`; state
  persistence is out of scope (points at `steering/00-project-overview.md` /
  `steering/02-engineering.md` and `WatermarkStore`).

- **`_dump_graph_payload`** — extend with a `zip(graph.nodes, payload["nodes"], strict=True)` loop
  that pops `"cursor"` from a dumped node when `node.cursor is None`. Both `dump_graph_to_yaml` and
  `dump_graph_to_json` inherit the behavior for free; update their docstrings to mention the
  cursor-omission alongside the existing join-omission note.

### Files to touch / create

| File | Change |
|---|---|
| `src/dander/pipeline/graph.py` | Add `CursorKind`, `CursorStrategy` (+ validator + classmethod); add `Node.cursor`; extend `_dump_graph_payload` and the two dump docstrings. |
| `src/dander/ingestion/source.py` | Docstring-only: annotate `Endpoint.incremental_cursor` as the legacy narrow form superseded by `pipeline.graph.CursorStrategy`, pointing at `from_incremental_cursor`. Keep the field so existing connector YAML loads. No behavior change. |
| `src/dander/pipeline/README.md` | New "Node cursor / watermark strategy" section; add the `Node.cursor` → `cursor` (omitted-when-`None`) row to the on-disk keys table; note the `incremental_cursor` migration and TIMESTAMP-default assumption; add related-ticket + Decision Log status line. |
| `tests/pipeline/test_graph_cursor.py` (new) | pytest suite mirroring `tests/pipeline/test_graph_join.py` (see Test seams). |

**Not re-exported from `dander/pipeline/__init__.py`** — following the merged precedent that the
finer-grained model classes (`JoinSpec`, `TransformationKind`, etc.) are imported from the submodule,
not the package root (documented in the README's "Import paths" section). `CursorKind`/
`CursorStrategy` follow suit: import from `dander.pipeline.graph`. (If the Code agent judges the
asymmetry worth closing, do it for all of them in a separate change, not silently here.)

### Trade-offs

- **Node attribute vs. free-form `Node.config`.** A typed `Node.cursor` costs one more model but buys
  boundary validation, type-safety, and stable serialization; burying it in `config` would make it
  invisible to mypy and unvalidated. Chosen: typed attribute, matching `Edge.join`.
- **Supersede vs. remove `Endpoint.incremental_cursor`.** Removing it would break existing connector
  YAML (violates the backward-compat AC). Chosen: keep + document + provide a clean mapping helper.
- **Free-form `params` vs. per-kind typed param models.** A discriminated union of per-kind param
  schemas would be more precise but is speculative generality no ticket asks for; the platform's
  precedent (`config`, `metadata`, opaque `expression`/`constant`) is free-form and inert. Chosen:
  free-form `params`, documented as opaque. Flagged below.
- **`kind` required vs. defaulted.** Unlike `Transformation.kind` (defaults to `DIRECT`),
  `CursorStrategy.kind` is required — there is no sensible "default cursor kind," and the AC frames
  kind as intrinsic to the strategy.

### Test seams

New `tests/pipeline/test_graph_cursor.py`, structured like `test_graph_join.py`, no network, using
`tmp_path`. Everything is pure model/serialization — nothing to mock. Coverage maps 1:1 to the ACs:

- **Load each kind from YAML and JSON.** A node loads a `CursorStrategy` for `timestamp`, `sequence`,
  and `opaque_token` (parametrized over the three kinds × both formats), asserting `field`, `kind`,
  and `params`/`metadata`.
- **Boundary constraint.** `CursorStrategy(field="", kind=...)` and a whitespace-only `field` each
  raise `ValidationError`; an out-of-set `kind` raises `ValidationError`.
- **Round-trip stability.** load → dump → load equality for a cursor-bearing graph, in both YAML and
  JSON (both the single load→dump→load and the dump-again idempotence check, matching the join tests).
- **Cursor-less node unchanged.** A node with `cursor is None` dumps with **no** `cursor` key
  (assert `"cursor" not in text`) in both formats and round-trips equal.
- **Direct construction + migration helper.** `CursorStrategy(...)` builds by attribute name;
  `from_incremental_cursor(None)`/`("")` → `None`; `from_incremental_cursor("updated_at")` →
  `CursorStrategy(field="updated_at", kind=CursorKind.TIMESTAMP)`.

No fixtures carry real or sensitive data (fake field names like `updated_at`, `row_seq`).

### Flags / ambiguities for the Code agent

1. **Naming.** The state layer uses "watermark" (`WatermarkStore`); this model is named
   `CursorStrategy` (concise, reads well as `node.cursor`) with a docstring tying it to the
   watermark/cursor contract. If the reviewer prefers `WatermarkStrategy` for symmetry with
   `WatermarkStore`, it's a rename only — no structural impact.
2. **TIMESTAMP mapping default.** `from_incremental_cursor` assumes a legacy `incremental_cursor` is
   timestamp-kind. This is documented, but it is an assumption — a legacy sequence/token cursor needs
   an explicit node-level strategy. Called out in the docstring and README migration note.
3. **`params` is intentionally un-schema'd.** No per-kind param validation (beyond "field
   non-empty") is in scope; the AC's "any params that kind needs" is satisfied by the free-form,
   opaque `params` dict, consistent with the rest of the package. If per-kind param constraints are
   later wanted, that is a follow-up ticket.
4. **Decision Log.** Surfacing the cursor strategy on the graph node (like DANDER-7 did for joins) is
   a product-shaped call; note it in the README's "Decision Log status" section and flag that
   `steering/00-project-overview.md`'s Decision Log has no entry yet — do not silently add one.

## Implementation Notes

Implemented exactly per the Design section, in `src/dander/pipeline/graph.py`:

- **`CursorKind(StrEnum)`** — `TIMESTAMP` / `SEQUENCE` / `OPAQUE_TOKEN`, placed alongside the
  module's other `StrEnum` discriminators, immediately before `Node` (so `Node.cursor:
  CursorStrategy | None` resolves against an already-defined class, matching how `Trigger`
  precedes `Node.trigger`).
- **`CursorStrategy(BaseModel)`** — `field: str` (required), `kind: CursorKind` (required, no
  default), `params: dict[str, Any] = {}`, `metadata: dict[str, Any] = {}`. An `after`
  `model_validator` (`_check_field_present`) raises `ValueError` when `field` is empty or
  whitespace-only (`.strip()` check, matching `Transformation.EXPRESSION`'s treatment).
- **`CursorStrategy.from_incremental_cursor(cursor_field: str | None) -> CursorStrategy | None`**
  — pure classmethod; `None`/empty maps to `None`, a non-empty string maps to
  `CursorStrategy(field=cursor_field, kind=CursorKind.TIMESTAMP)`. Takes a plain `str | None`, so
  `dander.pipeline` gains no import dependency on `dander.ingestion`.
- **`Node.cursor: CursorStrategy | None = Field(default=None)`** — the direct analogue of
  `Edge.join`; docstring updated with the attribute note (optional, supersedes
  `Endpoint.incremental_cursor`, state persistence explicitly out of scope, points at
  `steering/00-project-overview.md` / `steering/02-engineering.md` / `WatermarkStore`).
- **`_dump_graph_payload`** — extended the existing per-node loop with `if node.cursor is None:
  dumped_node.pop("cursor", None)`, so a cursor-less node dumps with no `cursor` key (not
  `cursor: null`). Both dump-function docstrings updated to mention the cursor omission alongside
  the existing join/request/writer/trigger omissions.
- **`src/dander/ingestion/source.py`** — docstring-only change on
  `Endpoint.incremental_cursor`, documenting it as the legacy narrow form superseded by
  `dander.pipeline.graph.CursorStrategy`/`Node.cursor`, pointing at `from_incremental_cursor`. No
  behavior change; existing connector YAML (`connectors/greenhouse.yaml`) still loads unchanged.
- **`src/dander/pipeline/README.md`** — added a "Node cursor / watermark strategy" section
  (mirroring the join-spec section's shape), the `Node.cursor` row in the on-disk-keys table, the
  `CursorKind`/`CursorStrategy` import-path note, the `DANDER-18` related-ticket reference, and a
  Decision Log status paragraph flagging (not silently filling) that
  `steering/00-project-overview.md`'s Decision Log has no entry yet for putting the cursor
  strategy on the graph node — same treatment as the existing DANDER-7 join flag.
- **`tests/pipeline/test_graph_cursor.py`** (new) — 19 tests, structured like
  `test_graph_join.py`: each `CursorKind` loads from both YAML and JSON (parametrized); a
  metadata-bearing cursor loads from both formats; boundary-constraint rejections (empty field,
  whitespace-only field, out-of-set kind); direct construction; YAML/JSON round-trip stability
  (including the dump-again idempotence check); a cursor-less node round-trips unchanged and
  omits the `cursor` key in both formats; a cursor-bearing node dumps a nested `cursor` block in
  both formats; and the three `from_incremental_cursor` cases (`None`, `""`, a real field name).
  No network; no real/sensitive fixture data (synthetic field names only: `updated_at`,
  `row_seq`, `next_token`).

**No deviations from the Design.** Both flagged ambiguities were resolved as the Design's stated
default: kept the `CursorStrategy` name (not renamed to `WatermarkStrategy`); left `params`
free-form/un-schema'd. `CursorKind`/`CursorStrategy` are not re-exported from
`dander.pipeline.__init__` (import from `dander.pipeline.graph`), consistent with the existing
`JoinSpec`/`TransformationKind` precedent.

**Tooling (all green):**
- `uv run ruff check src/dander/pipeline/graph.py src/dander/ingestion/source.py tests/pipeline/test_graph_cursor.py` — passed.
- `uv run ruff format --check` on the same files — already formatted.
- `uv run mypy src/` (whole package) — `Success: no issues found in 28 source files`.
- `uv run pytest -q` (whole suite) — 274 passed (19 new + 255 pre-existing/concurrent).

Note: `uv run ruff check .` (repo-wide) flags one pre-existing E501 in
`scripts/watch_workflows.py`, a file untouched by this ticket and outside its scope — not
introduced by this change.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed the implementation against all acceptance criteria, the steering files
(`01-security.md`, `02-engineering.md`, `languages/python.md`), and the approved Design.
Inspected the actual changed code: `src/dander/pipeline/graph.py`,
`src/dander/ingestion/source.py`, `src/dander/pipeline/README.md`, and the new
`tests/pipeline/test_graph_cursor.py`.

**Acceptance criteria — all met:**

1. Declarative model — `CursorStrategy(field: str, kind: CursorKind, params, metadata)` with a
   closed `CursorKind` StrEnum (`timestamp`/`sequence`/`opaque_token`), fully type-annotated.
   Verified.
2. Surfaced at node level — `Node.cursor: CursorStrategy | None = None`, the direct analogue of
   `Edge.join`. `Endpoint.incremental_cursor` kept (backward-compat) and documented as the legacy
   narrow form, with the clean `from_incremental_cursor` mapping bridge (plain `str | None`, so
   `pipeline` gains no `ingestion` import dependency). Migration documented in the source docstring
   and README. Verified.
3. Boundary constraint — `_check_field_present` after-validator rejects empty/whitespace-only
   `field` via `.strip()`, surfaced as a Pydantic `ValidationError`. No state read/written/persisted
   anywhere. Verified.
4. Backward compatibility — `cursor` optional, defaults to `None`; `_dump_graph_payload` pops the
   `cursor` key when `node.cursor is None` (scoped pop, not blunt `exclude_none`), mirroring the
   existing `join`/`trigger`/`request`/`writer` handling. Cursor-less node round-trips byte-identical;
   test asserts `"cursor" not in text` for both formats. Verified.
5. YAML/JSON round-trip stability — covered for cursor-bearing graphs including dump-again
   idempotence, both formats. Verified.
6. Google-style docstrings reference the control-table/idempotency design in
   `steering/00-project-overview.md`/`02-engineering.md` and `WatermarkStore`, explicitly note state
   persistence is out of scope, and are typed per `languages/python.md`. No secrets in fixtures
   (synthetic `updated_at`/`row_seq`/`next_token` only). Verified.
7. Tests — 19 tests: each kind from YAML and JSON (parametrized), metadata-bearing load, boundary
   rejections (empty/whitespace field, out-of-set kind), direct construction, YAML/JSON round-trip
   + idempotence, cursor-less round-trip with no `cursor` key, nested-block dump, and the three
   `from_incremental_cursor` cases. Under `tests/`, no network. Verified.
8. Tooling green (re-run during review): `uv run ruff check` on the changed files —
   "All checks passed!"; `uv run ruff format --check` — "3 files already formatted"; `uv run mypy
   src/` — "Success: no issues found in 28 source files"; `uv run pytest` — 266 passed. Verified.
   (The one `PytestCollectionWarning` for `TestKind` is pre-existing from DANDER-17, not introduced
   here.)
9. Scope respected — model + validation + serialization + tests only; no control-table persistence,
   no state I/O. Both Design flags resolved to the stated defaults (kept `CursorStrategy` name;
   `params` left free-form). The Decision Log entry was correctly flagged (in the README) rather than
   silently added.

**Security:** grepped the DANDER-18 diff for credential-shaped literals — only docstring guidance
about not embedding secrets; no hardcoded secrets, no PII/sensitive data in fixtures or logs. No
`.env.example` change needed (no new secret keys).

**Design fidelity:** implementation matches the approved Design exactly; Implementation Notes
accurately describe the change. No blocking issues.

Status set to `done`.
