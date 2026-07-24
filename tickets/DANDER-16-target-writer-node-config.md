---
id: DANDER-16
title: Target/writer node config schema
status: done
component: python
epic: pipeline-config
depends_on: [DANDER-10]
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (see DANDER-10 for the shared
review context).

A `target` node cannot yet declare **how and where it writes**. The write pattern (SCD1 / SCD2 /
snapshot / incremental — see `WriteMode` in `src/dander/writer/base.py`), the destination dataset /
table, and partitioning / clustering are unrepresented in any node config schema.

This ticket adds a typed **target/writer node config** to the discriminated `target`-node config
introduced in DANDER-10: it declares the write pattern (reusing/aligning with the writer's
`WriteMode`), the destination (dataset/table, aligning with `WriteTarget`), and partitioning /
clustering. Model + serialization + validation only — no writes and no BigQuery calls happen here.

## Acceptance Criteria

- [ ] A typed target/writer config on the `target`-node config (DANDER-10) capturing at least: write
      pattern (aligned with `WriteMode` in `src/dander/writer/base.py` — SCD1/SCD2/snapshot/
      incremental), destination dataset + table, and partitioning/clustering. Fully type-annotated.
- [ ] Reuses the existing `WriteMode` (and aligns with `WriteTarget` where practical) rather than
      re-declaring a parallel write-mode enum. Constraints are enforced at the Pydantic boundary
      (e.g. a valid write pattern; a business key present where the pattern needs one), raising a
      clear validation error.
- [ ] Backward compatibility: a target node without the new fields still loads/round-trips as far as
      the DANDER-10 typed shape allows.
- [ ] The target config round-trips stably through YAML and JSON via the existing load/dump functions
      (load → dump → load model equality).
- [ ] Google-style docstrings referencing the writer patterns in `src/dander/writer/base.py` and
      `steering/00-project-overview.md`; typed per `steering/languages/python.md`. No secrets in
      fixtures (dataset/table names are synthetic, non-sensitive).
- [ ] pytest tests cover: a target node loads its writer config for representative write patterns
      from YAML and JSON; boundary constraints reject an invalid pattern / missing required key;
      round-trip stability; and partitioning/clustering survive the round-trip. Tests live under
      `tests/`, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the target-config model + validation + serialization +
      tests. No write execution, no BigQuery client.

## Design

### Approach

DANDER-10 replaces the free-form `Node.config: dict[str, Any]` with a discriminated set of typed
per-node-type config models (expected `SourceNodeConfig` / `TransformNodeConfig` /
`TargetNodeConfig`, keyed by `Node.type`). This ticket extends **only** the `target` arm: it adds a
typed **writer config** describing *how and where* a target node writes, as an optional nested field
on `TargetNodeConfig`. It is model + validation + serialization only — no `WritePattern.write` call,
no BigQuery client, no `google.cloud` import anywhere in the diff.

The three concepts the ticket names map to three cohesive models, co-located with `TargetNodeConfig`:

1. **`WriteMode` is reused, not redeclared.** We import the existing `enum` from
   `src/dander/writer/base.py` (`from dander.writer.base import WriteMode`) and use it directly as
   the type of the write-pattern field. It is a `StrEnum`, so it already round-trips to/from its
   plain string value (`"scd1"`, `"scd2"`, `"snapshot"`, `"incremental"`) stably in YAML and JSON, and
   an out-of-set string fails at the Pydantic boundary with a clear `ValidationError`. The import
   direction is correct and non-circular: `pipeline` depends on the `writer` abstraction; `writer`
   never imports `pipeline`.

2. **The destination mirrors `WriteTarget`.** `WriteTarget` (frozen dataclass in `writer/base.py`)
   carries `project` / `dataset` / `table` / `business_key`. A new Pydantic `DestinationSpec`
   mirrors those field names 1:1 so the alignment is structural and a future writer-execution ticket
   can map config → `WriteTarget` trivially. Per `steering/languages/python.md`, the *config* object
   is Pydantic (boundary validation), while `WriteTarget` stays the internal runtime value object —
   we do **not** reuse the dataclass as a config model, and we do **not** add a `to_write_target()`
   converter here (that needs a runtime project fallback and is a write-execution concern — deferred,
   flagged below). `dataset` and `table` are required non-empty; `project` is optional (`None` = resolve
   from deployment context later); `business_key` is an ordered `list[str]` (maps to `WriteTarget`'s
   tuple), defaulting empty.

3. **Partitioning / clustering** get a `PartitioningSpec` model plus a `clustering: list[str]` field.
   Scope is BigQuery **time-unit** and **ingestion-time** partitioning (the common case, and what the
   `SNAPSHOT` "partitioned, append-only" pattern needs); integer-range partitioning is deferred as a
   future member (flagged). Clustering is capped at BigQuery's 4-column limit at the boundary.

Constraints the ticket calls for are enforced with a single `@model_validator(mode="after")` on
`WriterConfig` (the pattern already established by `Transformation._check_kind_payload` and
`JoinSpec` in `graph.py`): a business key must be present for the patterns that MERGE/version on it,
and an incremental write must name its watermark cursor. Because these are **presence-of-value**
checks (non-empty list / non-empty string), not null-vs-omitted checks, they are naturally
round-trip-safe — unlike `Transformation.constant`, no `model_fields_set` gymnastics are needed:
`model_dump` re-emits `business_key: []` / `cursor_field: null` and reload re-validates identically.

Backward compatibility is achieved by making the whole `writer` field **optional** on
`TargetNodeConfig` (`WriterConfig | None = None`): a target node authored before this ticket (no
writer block) loads and round-trips unchanged as a `TargetNodeConfig` with `writer=None`. Model
equality (the AC's actual bar) holds because reload maps the absent/`null` writer back to `None`.
Optionally, to preserve the *cosmetic* "absent-when-unset" cleanliness that `_dump_graph_payload`
already gives join-less edges, DANDER-10's node-config dump path may drop a `writer` key whose value
is `None` using the same targeted-omission technique — cosmetic only, not required for the equality
tests.

### Interfaces / classes (all in the node-config module introduced by DANDER-10)

- **`PartitioningType(StrEnum)`** — closed set of time-unit granularities: `HOUR` / `DAY` / `MONTH` /
  `YEAR` (matches the convention of `WriteMode`, `Materialization`, `JoinType`). Serializes to/from
  its plain string; invalid value → `ValidationError`.
- **`PartitioningSpec(BaseModel)`** — `field: str | None` (the partition column; `None` = ingestion-time
  partitioning on `_PARTITIONTIME`), `granularity: PartitioningType = PartitioningType.DAY`,
  `require_partition_filter: bool = False`. `model_config = ConfigDict(populate_by_name=True)`.
- **`DestinationSpec(BaseModel)`** — mirrors `WriteTarget`: `project: str | None = None`,
  `dataset: str` (non-empty), `table: str` (non-empty), `business_key: list[str] = Field(default_factory=list)`.
  Names/table are synthetic in fixtures — never secrets (`steering/01-security.md`).
- **`WriterConfig(BaseModel)`** — the ticket's core object:
  - `write_mode: WriteMode` (reused enum; required).
  - `destination: DestinationSpec` (required).
  - `cursor_field: str | None = None` — watermark column; required non-empty for `INCREMENTAL`
    (aligns with the "watermark-bounded" `WriteMode.INCREMENTAL` and the cursor-per-source mandate in
    `steering/02-engineering.md`).
  - `partitioning: PartitioningSpec | None = None`.
  - `clustering: list[str] = Field(default_factory=list, max_length=4)`.
  - `@model_validator(mode="after") _check_mode_requirements`: for `SCD1` / `SCD2` / `INCREMENTAL`,
    `destination.business_key` must be non-empty (MERGE / versioning / merge-on-key need a key);
    `SNAPSHOT` (append-only) is permissive on `business_key`. For `INCREMENTAL`, `cursor_field` must be
    a non-empty string. Clustering columns must be unique (BigQuery rejects duplicates). Each failure
    raises a `ValueError` with a clear, secret-free message naming the mode and the missing constraint.
- **`TargetNodeConfig`** (owned by DANDER-10) — extended with one field: `writer: WriterConfig | None = None`.

### Files to touch / create

- **`src/dander/pipeline/node_config.py`** (the module DANDER-10 introduces for the typed configs) —
  add `PartitioningType`, `PartitioningSpec`, `DestinationSpec`, `WriterConfig`; add the `writer`
  field + Google-style docstrings referencing `src/dander/writer/base.py` and
  `steering/00-project-overview.md` to `TargetNodeConfig`. If DANDER-10 lands the target config under
  a different module/name, add these there and adjust the import — the design is otherwise unchanged.
- **`src/dander/pipeline/__init__.py`** — export the new public models if the package re-exports the
  DANDER-10 configs (follow whatever DANDER-10 establishes).
- **`tests/pipeline/test_target_writer_config.py`** (new) — the writer-config test module.
- No change to `graph.py`'s load/dump functions is required: `load_graph_from_yaml/json` and
  `dump_graph_to_yaml/json` already drive validation/serialization through the model tree, so the
  new nested models round-trip for free once `TargetNodeConfig` carries them. (Only the optional
  cosmetic `writer:null` omission, if adopted, would touch `_dump_graph_payload`.)

### Trade-offs

- **Reuse `WriteMode` vs. a parallel pipeline-side enum** → reuse (AC mandate); a second enum would
  drift from the writer and is the exact anti-pattern the ticket calls out.
- **Nested `DestinationSpec` mirroring `WriteTarget` vs. flat fields on `WriterConfig`** → nested, so
  the config aligns 1:1 with `WriteTarget`'s grouping and a later converter is a trivial field map;
  it also keeps `WriterConfig` focused (SRP).
- **Pydantic config model vs. reusing the `WriteTarget` frozen dataclass** → Pydantic, per
  `python.md` ("Pydantic v2 for all config objects; frozen dataclass for internal value objects").
  `WriteTarget` stays the runtime value object.
- **No `to_write_target()` converter here** → deferred. `WriteTarget.project` is required while config
  `project` is optional, so a converter needs a runtime project fallback — a write-execution concern
  outside this ticket's "no writes" scope. Alignment is achieved by mirrored field names alone.
- **Time-unit + ingestion-time partitioning only (integer-range deferred)** → avoids speculative
  generality (`02-engineering.md`); a new `PartitioningType`/optional range field extends it later
  without touching callers.
- **`SNAPSHOT` permissive on `business_key`** → append-only never merges on a key, so a stray key is
  harmless; erroring would add friction with no correctness benefit. (Flagged for review.)

### Test seams

Pure Pydantic models — **no network, no I/O beyond the tmp-path YAML/JSON round-trip**, nothing to
mock. `tests/pipeline/test_target_writer_config.py` covers:

- **Representative-pattern load**, YAML and JSON, via `load_graph_from_yaml` / `load_graph_from_json`:
  a `target` node whose `writer` declares `SCD1` (+ business_key), `SCD2` (+ business_key), `SNAPSHOT`
  (no key), and `INCREMENTAL` (+ cursor_field + business_key).
- **Boundary rejections** (`pytest.raises(ValidationError)`): an invalid `write_mode` string; `SCD1`
  with empty `business_key`; `INCREMENTAL` missing `cursor_field`; >4 clustering columns; duplicate
  clustering columns.
- **Round-trip stability** in both formats: `load → dump → load` yields an equal `PipelineGraph`
  (model equality), including a `WriterConfig` populated with `partitioning` + `clustering`.
- **Partitioning/clustering survival**: assert `PartitioningSpec` fields and `clustering` order are
  identical across the round-trip.
- **Backward compatibility**: a `target` node with **no** `writer` block loads (`writer is None`) and
  round-trips unchanged.

Fixtures use synthetic, non-sensitive dataset/table names (e.g. `analytics`, `dim_candidate`) — no
secrets, no real data (`steering/01-security.md`).

### Flags for the Code agent / reviewer

- **Hard dependency on DANDER-10's realized shape.** DANDER-10 is not yet implemented. This design
  assumes it lands a `TargetNodeConfig` Pydantic model in `src/dander/pipeline/node_config.py` reached
  through the existing `load_graph_*/dump_graph_*` functions. If DANDER-10 chooses a different module,
  class name, or discrimination mechanism, keep the models above verbatim and only adjust the host
  module and the `writer`-field attachment point. Do not start this ticket before DANDER-10 is `done`.
- **`SNAPSHOT`/`business_key` permissiveness** and **partitioning scope (time-unit + ingestion-time
  only)** are deliberate scoping decisions — confirm they match reviewer expectations.

## Implementation Notes

Implemented exactly as designed — DANDER-10 had landed with the expected shape
(`TargetNodeConfig` in `src/dander/pipeline/node_config.py`), so no host-module/attachment-point
adjustment was needed.

**Files changed:**

- `src/dander/pipeline/node_config.py` — added `PartitioningType(StrEnum)` (`HOUR`/`DAY`/`MONTH`/
  `YEAR`), `PartitioningSpec`, `DestinationSpec` (mirrors `WriteTarget`'s `project`/`dataset`/
  `table`/`business_key`), and `WriterConfig` (`write_mode: WriteMode` reused directly from
  `dander.writer.base`, `destination`, `cursor_field`, `partitioning`, `clustering`, plus the
  `_check_mode_requirements` `@model_validator(mode="after")`). Extended `TargetNodeConfig` with
  `writer: WriterConfig | None = None`. Added the `WriteMode` import alongside the existing
  `RequestSpec` import, with the same `# noqa: TC001` justification (Pydantic resolves the
  `from __future__ import annotations`-deferred string annotation against module globals at
  class-definition time; a `TYPE_CHECKING`-only import breaks model construction).
- `src/dander/pipeline/__init__.py` — exported `WriterConfig`, `DestinationSpec`,
  `PartitioningSpec`, `PartitioningType`.
- `src/dander/pipeline/graph.py` — extended `_dump_graph_payload` (and its docstring, plus
  `dump_graph_to_yaml`/`dump_graph_to_json`'s docstrings) with the same targeted-omission
  technique already used for join-less `join` and spec-less `request`: a `target` node whose
  `TargetNodeConfig.writer is None` now omits the `writer` key entirely on dump, rather than
  emitting `writer: null`. This was flagged in the design as optional/cosmetic; implemented for
  consistency with the existing `request`/`join`/`trigger` omission behavior, and it is asserted
  in `test_target_node_with_no_writer_block_loads_and_round_trips`.
- `tests/pipeline/test_target_writer_config.py` (new) — covers representative-pattern loads
  (SCD1/SCD2/SNAPSHOT/INCREMENTAL) from YAML and JSON; boundary rejections (invalid `write_mode`,
  SCD1 with empty `business_key`, INCREMENTAL missing `cursor_field`, >4 clustering columns,
  duplicate clustering columns); YAML and JSON round-trip stability (`load -> dump -> load` model
  equality); partitioning/clustering survival across round-trip; and backward compatibility (a
  `target` node with no `writer` block, and one with no `config` key at all).

**Deviations from the design:** none. `SNAPSHOT` is permissive on `business_key` and partitioning
scope is time-unit/ingestion-time only, exactly as flagged in the design for reviewer confirmation.

**Toolchain:** `uv run ruff check`, `uv run ruff format --check`, and `uv run mypy` are clean on
all changed files (and on the full `src/dander` tree). `uv run pytest tests/` — 230 passed, 0
failed (up from the pre-ticket baseline). Note: `uv run ruff check` over the *whole* repo reports
one pre-existing `E501` in `scripts/watch_workflows.py` (a line at 102 chars); that file is
untouched by this diff (last touched in commit `7a75efa`, before this ticket) and is not part of
this ticket's scope.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed implementation against all acceptance criteria and steering. Verdict: **PASS**.

**Acceptance criteria — all met:**

1. Typed writer config present — `WriterConfig` on `TargetNodeConfig.writer` captures `write_mode`
   (aligned with `WriteMode`), `destination` (dataset/table via `DestinationSpec`), `partitioning`
   (`PartitioningSpec`), and `clustering`. Fully type-annotated.
2. `WriteMode` reused directly via `from dander.writer.base import WriteMode` (no parallel enum);
   `DestinationSpec` mirrors `WriteTarget`'s `project`/`dataset`/`table`/`business_key` 1:1.
   Constraints enforced at the Pydantic boundary: out-of-set `write_mode` rejected; the
   `_check_mode_requirements` `@model_validator(mode="after")` requires a non-empty `business_key`
   for SCD1/SCD2/INCREMENTAL, a non-empty `cursor_field` for INCREMENTAL, and rejects duplicate
   clustering columns; `max_length=4` caps clustering. Clear, secret-free `ValueError` messages.
3. Backward compatibility verified — `writer: WriterConfig | None = None`; a target node with no
   `writer` block (and one with no `config` at all) loads as `writer=None` and round-trips equal.
4. YAML and JSON round-trip stability confirmed by tests (`load -> dump -> load` model equality),
   both formats.
5. Google-style docstrings reference `src/dander/writer/base.py` and
   `steering/00-project-overview.md`; typed per `languages/python.md`. Fixtures use synthetic,
   non-sensitive names (`analytics`/`dim_candidate`/etc.) — no secrets.
6. Test coverage complete: representative patterns (SCD1/SCD2/SNAPSHOT/INCREMENTAL) from YAML and
   JSON; boundary rejections (invalid mode, empty business key, missing cursor, >4 / duplicate
   clustering); round-trip stability; partitioning/clustering survival; backward compat. Under
   `tests/`, no network.
7. Toolchain green: `ruff check`, `ruff format --check`, `mypy` all clean on the changed files and
   `src/dander/pipeline/`; `uv run pytest tests/` — **230 passed, 0 failed**.
8. No steering violations, no scope creep — model + validation + serialization + tests only. No
   write execution, no `google.cloud`/BigQuery client in the diff (grep confirms the only
   `google.cloud` token is a negation in a docstring). `hide_input_in_errors=True` guards against
   destination identifiers leaking into `ValidationError` text (security-conscious, consistent with
   `Node`/`RequestSpec`).

**Design fidelity:** matches the approved design exactly; the optional cosmetic `writer: null`
omission on dump was implemented in `_dump_graph_payload`, consistent with the existing
`request`/`join`/`trigger` omission behavior and asserted in tests. No deviations. The two flagged
scoping decisions (SNAPSHOT permissive on `business_key`; time-unit/ingestion-time partitioning
only, integer-range deferred) are confirmed as reasonable and non-blocking.

**Note (non-blocking):** the pre-existing `E501` in `scripts/watch_workflows.py` is outside this
ticket's diff and correctly excluded from scope.
