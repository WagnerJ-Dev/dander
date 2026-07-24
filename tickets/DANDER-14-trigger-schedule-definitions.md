---
id: DANDER-14
title: Trigger / schedule definitions for pipelines and nodes
status: done
component: python
epic: pipeline-config
depends_on: []
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (see DANDER-10 for the shared
review context).

Nothing today models **when** a pipeline or node runs. The Orchestration/State module in
`steering/00-project-overview.md` (scheduler + control table) is still a stub, and the declarative
model has no way to express a cron schedule, an upstream-dependency trigger, or a manual/event
trigger. This ticket is the **first concrete piece** of that module: a declarative trigger/schedule
representation attachable to a pipeline (and, where meaningful, a node).

Scope discipline: this is the declarative **model** for triggers only. It does not implement a
scheduler, wire up Cloud Scheduler / Cloud Run, or execute anything — those remain future
Orchestration work per the overview.

## Acceptance Criteria

- [ ] A declarative trigger/schedule representation covering at least: a cron schedule, an
      upstream-dependency trigger, and a manual/event trigger — modeled as a named closed set with
      the parameters each needs (e.g. a cron expression for the schedule kind). Fully type-annotated.
- [ ] The trigger is attachable at the pipeline level (and expressible per node where that makes
      sense); constraints are enforced at the Pydantic boundary (e.g. a cron kind requires a
      non-empty cron expression), raising a clear validation error. A cron expression is stored as an
      opaque string and is **not** evaluated/scheduled here.
- [ ] Backward compatibility: a pipeline/node with no trigger still loads and round-trips; triggers
      are optional.
- [ ] Triggers round-trip stably through YAML and JSON via the existing load/dump functions
      (load → dump → load model equality).
- [ ] Google-style docstrings noting this is declarative model only, executed by a future
      Orchestration layer per `steering/00-project-overview.md`; typed per
      `steering/languages/python.md`. No secrets in fixtures.
- [ ] pytest tests cover: a pipeline loads each trigger kind; boundary constraints reject a malformed
      trigger; round-trip stability in both formats; and a trigger-less pipeline is unchanged. Tests
      live under `tests/`, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the trigger model + validation + serialization + tests.
      No scheduler, no execution, no cloud wiring.

## Design

### Approach

This is a pure model + serialization extension to the existing pipeline-graph in
`src/dander/pipeline/graph.py`. Everything lives in that one module and reuses the primitives
DANDER-2 established (`BaseModel`, `ConfigDict`, `Field`, `StrEnum`, `model_validator`, and the
existing `load_*`/`dump_*` functions). No new module, no new dependency, no scheduler, no Cloud
Scheduler / Cloud Run wiring, and nothing is ever evaluated or executed — the graph records
declarative trigger **intent** only, which a future Orchestration/State layer will consume per
`steering/00-project-overview.md`. In particular a cron expression is stored as an **opaque
string** and is never parsed, validated as a cron grammar, or scheduled here.

The trigger is a closed, named set of kinds modelled with the **exact `Transformation` shape
already in this module** (DANDER-6): one `Trigger(BaseModel)` carrying a `kind` discriminator
(`TriggerKind(StrEnum)`) plus the kind-specific payload fields, with a single `@model_validator`
that enforces which payload each kind requires and forbids. Reusing that established pattern
(rather than a Pydantic discriminated union of one-model-per-kind) keeps the module internally
consistent, round-trips cleanly, and gives the future Orchestration layer a single importable type
to branch on. The three required kinds map to:

- **`SCHEDULE`** — a cron schedule. Payload: `cron: str | None`, an opaque cron expression.
  Required and non-empty for this kind; must be unset for the others.
- **`DEPENDENCY`** — an upstream-dependency trigger (fire when named upstream entities complete).
  Payload: `depends_on: list[str]`, upstream identifiers **by name/id only, never values**
  (`steering/01-security.md`). At least one required for this kind; must be empty for the others.
- **`MANUAL`** — a manual/event trigger. Payload: `event: str | None`, an optional opaque event
  name — `None` means a purely manual/on-demand trigger, a set string names an external event.
  No payload is required for this kind; `cron`/`depends_on` must be absent/empty.

The trigger is **attachable at both the pipeline and node level** as an optional field:
`PipelineGraph.trigger: Trigger | None = None` and `Node.trigger: Trigger | None = None`, both
defaulting to `None`. A pipeline-level trigger governs when the whole graph runs; a node-level
trigger (where meaningful) governs an individual node. The identifiers a `DEPENDENCY` trigger
names — upstream pipeline names at graph level, upstream node ids at node level — are interpreted
by the future Orchestration layer, not here; this ticket treats them as opaque strings and defers
any existence/resolution check.

**Backward compatibility & stable round-trip.** A pipeline/node that declares no trigger must
serialize byte-for-byte as it does today (no `trigger: null` key appearing). The module already
solved exactly this problem for the optional `Edge.join` field: `_dump_graph_payload` does **not**
use a blunt graph-wide `exclude_none` (that would also drop meaningful `None`s like an authored
`constant: null` on a `CONSTANT` transformation, breaking its reload), but instead pops only the
specific optional key after dumping. This design extends that same helper to pop the `trigger` key
from the graph payload when `graph.trigger is None`, and from each node's payload when that node's
`trigger is None` — leaving every other `None` untouched. A trigger that *is* present dumps its
full nested block. Round-trip stability (load → dump → load equality) then holds in both YAML and
JSON for triggered and trigger-less pipelines/nodes alike.

### Interfaces / classes (all in `src/dander/pipeline/graph.py`)

- **`TriggerKind(StrEnum)`** — the closed set of trigger kinds, mirroring the `TransformationKind`
  / `JoinType` convention (named, importable, serializes to a plain lowercase string, out-of-set
  value → `ValidationError`):
  - `SCHEDULE = "schedule"` — cron-driven.
  - `DEPENDENCY = "dependency"` — upstream-dependency-driven.
  - `MANUAL = "manual"` — manual/event-driven.

- **`Trigger(BaseModel)`** — the declarative trigger, opaque and inert:
  - `model_config = ConfigDict(populate_by_name=True)` — matches the sibling models.
  - `kind: TriggerKind` — **required** (no default): every trigger declares its kind, and a
    missing/invalid kind fails at the Pydantic boundary with a clear error. (Unlike
    `Transformation`, which had a natural `DIRECT` default, there is no meaningful default kind.)
  - `cron: str | None = None` — opaque cron expression for `SCHEDULE`. Never parsed or scheduled.
  - `depends_on: list[str] = Field(default_factory=list)` — upstream identifiers for `DEPENDENCY`;
    names/ids only.
  - `event: str | None = None` — optional opaque event name for `MANUAL`.
  - `metadata: dict[str, Any] = Field(default_factory=dict)` — optional free-form tags/labels only
    (never data/secrets), consistent with `Node.config` / `JoinSpec.metadata`.
  - `@model_validator(mode="after") _check_kind_payload` — enforces per-kind constraints, raising
    a clear `ValueError` (surfaced as a `ValidationError`) at the boundary:
    - `SCHEDULE`: `cron` must be present and non-empty (`cron is None or not cron.strip()` →
      error); `depends_on` must be empty; `event` must be unset.
    - `DEPENDENCY`: `depends_on` must be non-empty; `cron` must be unset; `event` must be unset.
    - `MANUAL`: `cron` must be unset; `depends_on` must be empty; `event` is optional (any value).
    The "forbidden" checks test the field **value** (`cron is None`, `not depends_on`,
    `event is None`) rather than `model_fields_set`, so that a dump→load cycle — which re-emits
    every field including defaults (`cron: null`, `depends_on: []`, `event: null`) — reloads
    without spuriously tripping the validator. This is the same value-vs-presence reasoning already
    documented on `Transformation._check_kind_payload`; none of these payloads has a meaningful
    `null` sentinel (unlike `Transformation.constant`), so value-based checks are lossless here.

- **`Node`** (existing) gains one field:
  - `trigger: Trigger | None = Field(default=None)` — optional per-node trigger; `None` (default)
    means the node carries no trigger and loads/dumps exactly as a pre-DANDER-14 node did.

- **`PipelineGraph`** (existing) gains one field:
  - `trigger: Trigger | None = Field(default=None)` — optional pipeline-level trigger; `None`
    (default) means the graph carries no trigger and loads/dumps exactly as before.

### Backward-compatible serialization (extend `_dump_graph_payload`)

Extend the existing helper (which today only pops join-less `join` keys) to also:
- `payload.pop("trigger", None)` when `graph.trigger is None`; and
- for each `node, dumped_node in zip(graph.nodes, payload["nodes"], strict=True)`, pop
  `dumped_node["trigger"]` when `node.trigger is None`.

No change to `dump_graph_to_yaml` / `dump_graph_to_json` themselves (they delegate to the helper),
and no change to the `load_*` functions (Pydantic parses the optional field natively). Nested
`Trigger` needs no alias handling — its attribute names are its on-disk keys — so the existing
`model_dump(by_alias=True, mode="json")` path serializes it unchanged when present. Update the
helper's docstring to note it now scopes the omission to both `join`-less edges and `trigger`-less
graphs/nodes, preserving all other `None`s.

### Files to touch

- **`src/dander/pipeline/graph.py`** — add `TriggerKind` and `Trigger` (with Google-style
  docstrings stating this is a declarative model only, executed by a future Orchestration layer per
  `steering/00-project-overview.md`, and that a cron expression is opaque/never evaluated); add the
  optional `trigger` field to `Node` and to `PipelineGraph`; extend `_dump_graph_payload` (and its
  docstring) to drop `trigger`-less keys at graph and node level.
- **`tests/pipeline/test_graph_trigger.py`** (new, alongside `test_graph_join.py`) — the trigger
  cases, reusing the file-based `tmp_path` + inline-doc pattern already established in the sibling
  graph tests.

### Test seams

Pure models and file round-trip only — no network, no mocking (matches every existing graph test).
Cases to add:
- A pipeline loads **each** trigger kind: a `SCHEDULE` at the graph level (cron string), a
  `DEPENDENCY` at graph level (non-empty `depends_on`), and a `MANUAL` at a **node** level (with
  and without an `event`) — from **both** YAML and JSON.
- Boundary constraints reject a malformed trigger via `pytest.raises(ValidationError)`:
  `SCHEDULE` with missing/empty/whitespace `cron`; `DEPENDENCY` with empty `depends_on`; a
  `SCHEDULE` that also sets `depends_on`/`event`; an unknown `kind` value; a trigger with no `kind`.
- Stable round-trip in **both** formats (load → dump → load equality) for a triggered pipeline
  (graph-level trigger + a node-level trigger + `metadata`) and for a `MANUAL` trigger with `event`
  unset (guards the value-vs-presence validator reasoning across a dump/load cycle).
- A **trigger-less** pipeline is unchanged: it round-trips equal *and* its dumped YAML/JSON text
  carries no `trigger` key at either the graph or node level (guards the `_dump_graph_payload`
  omission). No secrets or sensitive data in any fixture.

### Trade-offs

- **Single `Trigger` model with a `kind` discriminator vs. a discriminated union of one model per
  kind.** Chose the single-model + `model_validator` shape to match the established `Transformation`
  precedent in this exact module — it is internally consistent, round-trips cleanly through the
  existing dump helper, and gives one importable type. A discriminated union would be more
  "type-pure" per kind but diverges from house convention for no in-scope benefit.
- **`StrEnum` vs `Literal[...]` for `TriggerKind`.** `StrEnum` for parity with `TransformationKind`
  / `JoinType` / `WriteMode` / `Materialization`; closed-set boundary validation, plain-string
  on-disk form, and equality/round-trip for free. AC permits "a named closed set"; `StrEnum` is the
  house form.
- **`kind` required (no default).** Unlike `Transformation`'s natural `DIRECT` default, no trigger
  kind is a sensible default; requiring it makes a missing kind a clear boundary error and keeps
  each on-disk trigger self-describing.
- **`MANUAL` covering both manual and event via an optional `event` vs. two separate kinds.** The AC
  groups them ("a manual/event trigger") as one item; one kind with an optional opaque `event`
  string models both (unset = manual/on-demand, set = event-named) without a speculative fourth
  kind (`steering/02-engineering.md`: don't build what no ticket asks for).
- **Scoped `trigger`-key omission in `_dump_graph_payload` vs. graph-wide `exclude_none`.** Reused
  the module's existing scoped approach; a blunt `exclude_none` would drop meaningful `None`s
  elsewhere (notably an authored `constant: null`) and break their reload — the module already
  rejected that trade-off for `join`, and the same reasoning applies.
- **`depends_on` as opaque `list[str]` (no existence/resolution check).** Consistent with the
  module's deferral pattern (field/join references aren't resolved here either; that's DANDER-8 for
  fields). Resolving upstream identifiers belongs to the future Orchestration layer.

### Notes / flags

- **AC "expressible per node where that makes sense" is satisfied by adding the same optional
  `trigger` field to `Node`.** All three kinds are structurally valid on a node; whether a given
  kind is *semantically* appropriate on a node vs. only on a pipeline is an Orchestration-layer
  concern, not a model constraint — called out so PR-Review reads the uniform field as intentional,
  not an over-reach.
- **No timezone / catch-up / start-date fields on `SCHEDULE`.** These are real scheduling concerns
  but unasked-for here and belong to the future Orchestration layer; the AC scopes `SCHEDULE` to an
  opaque cron expression. Omitted deliberately to avoid speculative generality.
- **Cross-ticket ordering.** DANDER-14 edits `Node`, `PipelineGraph`, and `_dump_graph_payload` in
  `graph.py`. It is additive and non-conflicting with the sibling `graph.py` tickets (e.g.
  DANDER-13 targets `ingestion/source.py`; DANDER-15/16 add other kinds). If another `graph.py`
  change lands first, add the `trigger` field alongside the existing optional fields and extend the
  same `_dump_graph_payload` loop — no behavioral coupling with `mappings`/`join`.

## Implementation Notes

Implemented exactly per Design — no deviations.

- **`src/dander/pipeline/graph.py`**:
  - Added `TriggerKind(StrEnum)` (`SCHEDULE`/`DEPENDENCY`/`MANUAL`) and `Trigger(BaseModel)`,
    placed **before** `Node` in the module (not after `PipelineGraph` as the file narrative
    reads) — required because the module uses `from __future__ import annotations` and Pydantic
    v2 resolves those string annotations against module globals at class-build time; `Node`
    needed `Trigger` to already exist when its class body is processed, matching the file's
    existing top-down "define dependencies before use" ordering (`NodeField` before `Node`,
    `Transformation` before `FieldMapping`, etc.). `TriggerKind`/`Trigger` themselves are
    unchanged from the Design's spec.
  - `Trigger._check_kind_payload` enforces the per-kind required/forbidden payload exactly as
    specified: `SCHEDULE` requires non-empty `cron`, forbids `depends_on`/`event`; `DEPENDENCY`
    requires non-empty `depends_on`, forbids `cron`/`event`; `MANUAL` forbids `cron`/`depends_on`,
    `event` optional. Value-based checks (not `model_fields_set`), per the Design's
    dump-round-trip reasoning.
  - Added `trigger: Trigger | None = Field(default=None)` to both `Node` and `PipelineGraph`.
  - Extended `_dump_graph_payload` to pop the graph's `trigger` key when `graph.trigger is None`
    and each node's `trigger` key when `node.trigger is None`, alongside the existing `join`/
    `request` omission logic; updated its docstring and the `dump_graph_to_yaml`/
    `dump_graph_to_json` docstrings to mention the new omission.

- **`tests/pipeline/test_graph_trigger.py`** (new): covers every case in the ticket's Test seams —
  each trigger kind loading at graph level (`SCHEDULE`, `DEPENDENCY`) and node level (`MANUAL`,
  with and without `event`) from both YAML and JSON; boundary rejection via a parametrized
  `pytest.raises(ValidationError)` table (missing/empty/whitespace `cron`, empty `depends_on`,
  cross-kind payload leakage, unknown `kind`, missing `kind`); direct-construction sanity checks
  for all three kinds; stable round-trip (load→dump→load equality, doubled to catch any
  second-generation drift) in both formats for a pipeline with graph- and node-level triggers +
  metadata, and separately for a `MANUAL` trigger with `event` unset (guards the value-vs-presence
  validator reasoning across a dump/load cycle); a trigger-less pipeline round-trips unchanged
  with no `trigger` key in the dumped text (YAML and JSON); and a graph+node with triggers dump a
  nested `trigger` block with `kind` + payload visible in both formats. No network, no secrets/
  sensitive fixtures — cron strings and event names are synthetic.

- **Toolchain**: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, and
  `uv run pytest` (full suite, 196 tests) all pass. `ruff format` reformatted `graph.py` once
  (line-length wrap on two raised `ValueError` messages) — no logic change. Pre-existing
  unrelated failures in `scripts/watch_workflows.py` (one `ruff` E501, two `mypy` `type-arg`
  errors) were confirmed present on `main` before this change (verified via `git stash`) and are
  out of scope for this ticket.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed the implementation in `src/dander/pipeline/graph.py` and `tests/pipeline/test_graph_trigger.py`
against every acceptance criterion, the steering files, and `steering/languages/python.md`.

- **AC1 (closed trigger set, typed):** `TriggerKind(StrEnum)` with `SCHEDULE`/`DEPENDENCY`/`MANUAL`
  and `Trigger(BaseModel)` carrying `kind` + `cron`/`depends_on`/`event`/`metadata`, fully
  type-annotated. Matches the house `Transformation`/`JoinType` precedent. Met.
- **AC2 (attachable at pipeline + node; boundary constraints; opaque cron):**
  `PipelineGraph.trigger` and `Node.trigger`, both `Trigger | None = None`. `_check_kind_payload`
  enforces per-kind required/forbidden payload at the Pydantic boundary with clear `ValueError`s
  (SCHEDULE requires non-empty/non-whitespace `cron`; etc.). Cron is stored as an opaque string,
  never parsed/scheduled. Met.
- **AC3 (backward compat):** trigger optional; trigger-less graph/node round-trips equal and emits
  no `trigger` key — `test_trigger_less_pipeline_round_trips_unchanged_and_omits_trigger_key`. Met.
- **AC4 (stable round-trip YAML+JSON):** covered for graph+node triggers with metadata, plus a
  `MANUAL`-without-`event` case guarding the value-vs-presence validator across a dump/load cycle.
  `_dump_graph_payload` correctly extends the existing scoped-omission pattern (not a blunt
  `exclude_none`), preserving other meaningful `None`s. Met.
- **AC5 (docstrings + no secrets):** Google-style docstrings on `TriggerKind`/`Trigger`/validator/
  helpers state declarative-model-only intent, defer to the future Orchestration layer per
  `steering/00-project-overview.md`, and note cron is opaque; `depends_on` documented as names/ids
  only. Fixtures are synthetic (cron strings, `candidate.updated`, `upstream_pipeline_*`); no
  secrets/PII. Met.
- **AC6 (tests):** each kind loads from YAML+JSON (graph-level SCHEDULE/DEPENDENCY, node-level
  MANUAL with/without event), a 13-case parametrized malformed-payload table raises
  `ValidationError`, direct-construction sanity, round-trip stability both formats, trigger-less
  unchanged. Under `tests/`, no network. Met.
- **AC7 (green toolchain):** verified locally — `ruff check` + `ruff format --check` clean on the
  changed files, `mypy src tests` clean (41 files), `pytest` full suite green (205 passed).
- **AC8 (no scope creep / steering):** pure model + validation + serialization; no scheduler, no
  execution, no cloud wiring. Diff scanned for credential-shaped literals — none (only a docstring
  prohibition note). Interface-first and idempotency-neutral; consistent with the module.

No blocking issues. Status set to `done`.
