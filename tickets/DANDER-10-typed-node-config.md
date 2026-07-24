---
id: DANDER-10
title: Typed, per-node-type config on pipeline-graph nodes
status: done
component: python
epic: pipeline-config
depends_on: []
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (review of the current
`Node`/`Edge`/`NodeField`/`Transformation` model in `src/dander/pipeline/graph.py` and the
`SourceConfig`/`Endpoint` model in `src/dander/ingestion/source.py`, on top of DANDER-1..9).

`Node.config` is today an opaque `dict[str, Any]` for **every** node regardless of `type`. Nothing
validates that a `source` node's config actually looks like a source config, a `target` node's like
a target config, or a `transform` node's like a transform config. This violates the interface-first,
"config-driven with real shapes" mandate in `steering/02-engineering.md`.

This ticket introduces a **discriminated/typed config shape keyed by `Node.type`** (source /
transform / target), so each node type carries a validated config model instead of a free-form dict.
It is model + serialization + validation only — it does not populate the full detail of each config
(request/payload spec, pagination, write pattern) which are separate gap tickets. This ticket is a
**prerequisite** for DANDER-11 (source request/payload spec) and DANDER-16 (target/writer node
config), which extend the typed shapes it establishes.

## Acceptance Criteria

- [ ] A per-node-type config representation: distinct Pydantic models for at least `source`,
      `transform`, and `target` node config, selected/discriminated by `Node.type`. Fully
      type-annotated.
- [ ] `Node` validates at the Pydantic boundary that its `config` matches its declared `type` (a
      `source` node rejects a `target`-shaped config, and vice versa), raising a clear validation
      error naming the mismatch. No secrets in the error message.
- [ ] Backward compatibility: existing DANDER-2..9 graphs still load and round-trip. A node whose
      `type` has no stricter schema yet (or an as-yet-unmodeled type) still loads its config without
      spurious rejection; the migration path for the free-form `config`/`params` alias is preserved.
- [ ] Typed node config round-trips stably through **both** YAML and JSON via the existing
      load/dump functions: load → dump → load yields an equivalent graph (model equality).
- [ ] Google-style docstrings on new/changed public models; typed per `steering/languages/python.md`.
      No secret values in configs, defaults, or fixtures.
- [ ] pytest tests cover: each node type loads its typed config from YAML and JSON; a type/config
      mismatch is rejected at the boundary; round-trip stability in both formats; and backward
      compatibility with an existing free-form/unmodeled node. Tests live under `tests/`, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the discriminated config model + its validation +
      serialization + tests. The detailed payloads of each config are DANDER-11 / DANDER-16 and out
      of scope here.

## Design

### Approach

Today `Node.config` is a single `dict[str, Any]` that accepts the `config`/`params` alias and
validates nothing about shape. This ticket replaces the opaque dict with a **discriminated set of
typed config models keyed by `Node.type`**, while leaving `Node.type` an open string (DANDER-3 owns
type-value validation; `task` and future kinds must still load).

The discriminator (`Node.type`) is a **sibling field** of `config`, not a tag *inside* the config
object, so Pydantic's built-in `Field(discriminator=...)` (which reads a key within the union
member) does not apply directly. Instead we route with a **`field_validator("config", mode="before")`
on `Node`**: field validators run after alias resolution (so the existing `config`/`params`
`AliasChoices` keeps working for free) and receive `ValidationInfo`, whose `info.data` already holds
the earlier-declared, already-validated `type` (Pydantic validates fields in declaration order, and
`type` is declared before `config`). The validator looks up `type` in a small registry of config
models and routes the raw value to the matching model; for an unmodeled type it passes the value
through as a plain dict (backward compatibility).

Because this ticket is **model + validation + serialization only** — it does *not* populate the real
per-type fields (that is DANDER-11 for source request/payload and DANDER-16 for target/writer) — the
three typed models are deliberately **open placeholders** (`extra="allow"`, no required fields yet).
Two consequences follow, and both are intended:

1. **Round-trip is lossless now and stays lossless as the models grow.** Arbitrary current config
   content (e.g. a DANDER-2 `source` node carrying `{"endpoint": "/candidates"}`) is preserved as
   `extra` fields, survives dump → load, and compares equal (Pydantic v2 model equality includes
   `__pydantic_extra__`).
2. **Shape-mismatch enforcement bites on _typed instances_, not yet on raw dicts.** Since the models
   carry no distinguishing required fields yet, a wrong-shaped *raw dict* is structurally
   indistinguishable from a right one and cannot be rejected at this stage. What *is* unambiguous —
   and what AC #2 is satisfied by — is a **wrong typed-config instance**: constructing
   `Node(type="source", config=TargetNodeConfig(...))` is rejected with a clear error naming the
   mismatch. Once DANDER-11/16 add required fields, wrong raw dicts start failing on their own field
   validation with no change to this routing. This is called out under Trade-offs; see the flagged
   note on AC #2.

### Interfaces / classes

New module **`src/dander/pipeline/node_config.py`** (keeps the already-large `graph.py` focused on
graph shape, and gives DANDER-11/16 an obvious home to extend). `graph.py` imports from it; there is
no import cycle (`node_config` does not import `Node`).

- **`NodeType(StrEnum)`** — the closed set of *modeled* node kinds, following the established
  `TransformationKind`/`JoinType` convention (a named, importable, string-serializing enum). Members:
  `SOURCE = "source"`, `TRANSFORM = "transform"`, `TARGET = "target"`. This does **not** close
  `Node.type` (which stays `str`); it only names the types that currently have a stricter schema.

- **`NodeConfig(BaseModel)`** — common base for every typed node config.
  `model_config = ConfigDict(extra="allow", populate_by_name=True)`. Carries no fields of its own yet;
  it exists so `Node.config` can be annotated on the abstraction and so mismatch detection can test
  `isinstance(value, NodeConfig)`.

- **`SourceNodeConfig(NodeConfig)`**, **`TransformNodeConfig(NodeConfig)`**, **`TargetNodeConfig(NodeConfig)`**
  — the three distinct per-type models. Empty placeholders now (extra fields allowed); DANDER-11
  extends `SourceNodeConfig`, DANDER-16 extends `TargetNodeConfig`. They are distinct *classes* (not
  aliases) so instance-based mismatch detection is exact.

- **`_NODE_CONFIG_MODELS: dict[NodeType, type[NodeConfig]]`** — the registry mapping each modeled
  type to its config class. Keyed by `NodeType` members; because `StrEnum` members hash equal to
  their string value, a plain-string lookup `_NODE_CONFIG_MODELS.get(node_type)` (where `node_type`
  is `Node.type`, a `str`) resolves correctly.

- **`resolve_node_config(node_type: str, value: object) -> NodeConfig | dict[str, Any]`** — the pure,
  unit-testable routing function (the test seam). Logic:
  - Look up `model = _NODE_CONFIG_MODELS.get(node_type)`.
  - `model is None` (unmodeled type): return `value` if it is a `dict`, else `{}` for `None`/absent —
    unchanged free-form behavior.
  - `value` is already a `NodeConfig` instance: if `type(value) is model`, return it as-is; otherwise
    raise `ValueError` naming the mismatch (see error text below). This is the AC #2 rejection.
  - otherwise (`value` is a dict or `None`/absent): return `model.model_validate(value or {})` — the
    typed instance for that node type.
  - Raised `ValueError` surfaces as a Pydantic `ValidationError` because it is raised from inside
    `Node`'s field validator. Error text uses class names + `node_type` only, e.g.
    `"source node config expects SourceNodeConfig, got TargetNodeConfig"` — **no config values**, per
    `steering/01-security.md`.

- **`Node` (changed, in `graph.py`)**:
  - `config` annotation becomes `SerializeAsAny[NodeConfig] | dict[str, Any]`, keeping
    `default_factory=dict` and the existing `validation_alias=AliasChoices("config", "params")`, and
    adding `validate_default=True` so a known-type node with **no** config still routes to an empty
    typed model (e.g. `TargetNodeConfig()`), keeping `config` consistently typed for modeled types
    while an unmodeled type's absent config stays `{}`.
  - `SerializeAsAny[...]` is required so `model_dump` serializes the **concrete subclass** (including
    its `extra` fields and future DANDER-11/16 fields) rather than the base `NodeConfig`; without it
    Pydantic would serialize to the declared (base) type and drop subclass content.
  - Add `@field_validator("config", mode="before")` `_route_config` that returns
    `resolve_node_config(info.data["type"], value)`. `info.data["type"]` is guaranteed present
    because `type` is declared before `config`. (Pydantic's default `revalidate_instances="never"`
    means the returned typed instance is accepted without being re-coerced/downcast by the
    `NodeConfig | dict` union, preserving its concrete class and our mismatch decision.)

Nothing about `Edge`, `PipelineGraph`, the load/dump functions, or `graph_ops.py` changes: the
existing `_dump_graph_payload` already does `model_dump(by_alias=True, mode="json")`, which — with
`SerializeAsAny` — emits each typed config as a plain nested dict, so the YAML/JSON writers and the
join-key omission logic are untouched. `graph_ops.py` reads `node.config` nowhere, so it is
unaffected.

### Files to touch / create

- **Create `src/dander/pipeline/node_config.py`** — `NodeType`, `NodeConfig`, the three per-type
  models, `_NODE_CONFIG_MODELS`, and `resolve_node_config`. Google-style docstrings on every public
  symbol; module docstring stating responsibility. Each per-type model's docstring notes it is an
  extensible placeholder filled by DANDER-11 (source) / DANDER-16 (target) and that it must never
  hold a secret value (`steering/01-security.md`).
- **Edit `src/dander/pipeline/graph.py`** — import the new symbols; change `Node.config`'s annotation
  to `SerializeAsAny[NodeConfig] | dict[str, Any]` with `validate_default=True`; add the
  `_route_config` field validator; update `Node`'s class docstring to describe the discriminated
  typed config and the preserved free-form/alias migration path. Import `SerializeAsAny` and
  `field_validator` from `pydantic`.
- **Edit `src/dander/pipeline/__init__.py`** — export `NodeType`, `NodeConfig`, `SourceNodeConfig`,
  `TransformNodeConfig`, `TargetNodeConfig` (add to imports and `__all__`) so callers/tests import
  the typed configs from the package root, consistent with how `Node`/`Edge` are surfaced.
- **Edit `tests/pipeline/test_graph.py`** — update the two assertions that compare a modeled node's
  `config` to a bare dict (lines ~76–77: the `source` node `n1` and `target` node `n2`). They become
  typed-model comparisons, e.g. `graph.nodes[0].config == SourceNodeConfig(endpoint="/candidates")`
  and `graph.nodes[1].config == TargetNodeConfig()` (or compare `.model_dump()`). All other existing
  tests use `type="task"` (unmodeled → `config` stays a plain dict) and remain unchanged — verified
  by grep: `test_graph.py:127/135` (`params`/mutation) are `task` nodes, and no other test reads
  `.config`.
- **Create `tests/pipeline/test_node_config.py`** — the new coverage (below). Splitting from
  `test_graph.py` mirrors the existing `test_graph_join.py` / `test_transformations.py` layout.

### Tests (what gets unit-tested / mocked)

No network, no I/O beyond `tmp_path` for the round-trip cases (matching existing tests). Cover:

- **Per-type typed load** from **both** YAML and JSON: a `source`/`transform`/`target` node loads
  its `config` as the corresponding `SourceNodeConfig`/`TransformNodeConfig`/`TargetNodeConfig`
  (`isinstance` + a representative `extra` field preserved).
- **Mismatch rejection at the boundary**: `Node(type="source", config=TargetNodeConfig())` (and the
  reverse) raises `pydantic.ValidationError`; assert the message names both class names / the type
  and contains **no** config values.
- **Round-trip stability, both formats**: a graph mixing all three modeled node types (with some
  `extra` config content) satisfies load → dump → load == load, for YAML and JSON, via the existing
  `dump_graph_to_*`/`load_graph_from_*`.
- **Backward compatibility**: (a) an **unmodeled** type (`task`) keeps its free-form dict config and
  round-trips unchanged; (b) the `params` alias still populates `config`; (c) a modeled node with
  **no** config loads as an empty typed model and round-trips; (d) a pre-existing DANDER-2-style
  graph (`source`→`target` with arbitrary config content) still loads and round-trips equal.
- **`resolve_node_config` unit tests** directly (the pure seam): known type + dict → typed instance;
  known type + correct instance → same instance; known type + wrong instance → `ValueError`;
  unmodeled type + dict → same dict; `None`/absent handling.

### Trade-offs

- **Sibling-field discrimination via a field validator vs. an in-config `Literal` discriminator.**
  Putting a `kind: Literal["source"]` inside each config model would let us use Pydantic's native
  discriminated union, but it duplicates `Node.type` into every config payload, leaks a redundant
  key into the serialized YAML/JSON, and creates a second source of truth that could disagree with
  `Node.type`. Routing on the existing `Node.type` via a field validator keeps a single
  discriminator and a clean on-disk shape. Chosen.
- **Open placeholder models (`extra="allow"`) vs. strict-now.** Strict models would reject the
  arbitrary config content that DANDER-2..9 graphs already carry (violating the backward-compat AC)
  and would pre-empt DANDER-11/16's field design. Open-now, strict-as-populated is the correct
  increment and keeps this ticket to *shape + validation + serialization*.
- **New module vs. inlining in `graph.py`.** A dedicated `node_config.py` avoids further growing
  `graph.py` and localizes the surface DANDER-11/16 will extend, at the cost of one more import.
  Worth it given those follow-on tickets.
- **`SerializeAsAny` requirement.** Annotating on the `NodeConfig` base is the clean, DIP-aligned
  choice, but Pydantic serializes to the *declared* type by default; `SerializeAsAny` is the
  explicit, documented tool to serialize the runtime subclass. Noted so the Code agent does not omit
  it (its omission would silently drop config content on dump).

### Flagged for the Code agent / reviewer

- **AC #2 scope clarification (not a gap, but call it out in the PR):** with the placeholder models
  unpopulated, "a source node rejects a target-shaped config" is enforced for a **wrong typed
  `NodeConfig` instance**, which is the only unambiguous signal available before DANDER-11/16 add
  distinguishing fields. Raw-dict shape rejection arrives automatically once those tickets add
  required fields — no rework to the routing. If the reviewer reads AC #2 as also requiring raw-dict
  rejection *now*, that cannot be done without inventing per-type required fields, which is
  explicitly out of scope here (AC #8) and owned by DANDER-11/16.

## Implementation Notes

Implemented per the Design section, with two deviations forced by verified Pydantic runtime
behavior (both re-checked against `pydantic==2.13.4`, the pinned version in this environment):

1. **`Node.config` union order + `union_mode="left_to_right"`, not smart-mode
   `SerializeAsAny[NodeConfig] | dict[str, Any]`.** Verified by direct repro: with Pydantic's
   default *smart* union mode, a plain `dict` input (e.g. an unmodeled `task` node's `config`)
   was **not** kept as `dict` — Pydantic preferred coercing it into the (structurally-compatible,
   `extra="allow"`, no-required-fields) `NodeConfig` model, silently breaking AC #3's backward
   compatibility (an unmodeled type's config must stay a plain dict). Fix: annotate
   `config: dict[str, Any] | SerializeAsAny[NodeConfig]` (dict first) with
   `Field(..., union_mode="left_to_right")`. Verified this still preserves the concrete typed
   subclass (e.g. `SourceNodeConfig`, not downcast to base `NodeConfig`) when `_route_config`
   returns an already-typed instance, because a `NodeConfig`/subclass instance is not itself a
   `dict` so the first union member fails over correctly, and (Pydantic's default
   `revalidate_instances="never"`) the second member accepts it without re-coercion. All
   round-trip/backward-compat/mismatch tests pass with this shape; `_NODE_CONFIG_MODELS` and
   `resolve_node_config` are otherwise exactly as designed.
2. **`Node.model_config` adds `hide_input_in_errors=True`.** Without it, the AC #2 requirement
   ("no secrets in the error message") did not hold in practice: Pydantic's `ValidationError`
   rendering appends the rejected input's `repr()` (`input_value=TargetNodeConfig(table=...)`,
   etc.) after any raised `ValueError` text, regardless of how careful the raised message itself
   is. Verified this leak with a live repro before fixing, and verified `hide_input_in_errors`
   suppresses it while keeping the raised message (`"source node config expects
   SourceNodeConfig, got TargetNodeConfig"`) intact. Tests assert the offending config values are
   absent from the exception string, not just that class names are present.
3. **`_NODE_CONFIG_MODELS` typed `dict[str, type[NodeConfig]]`, not `dict[NodeType, ...]`.** The
   design's literal annotation, combined with the plain-`str` `.get(node_type)` lookup it
   prescribes, does not pass `mypy --strict` (a `str` key against a `dict[NodeType, ...]`'s
   invariant `_KT` is not accepted, since `NodeType` is a narrower type than `str`). Keying the
   registry's declared type as `dict[str, type[NodeConfig]]` (values still assigned from
   `NodeType` members, which are `str` instances) keeps the lookup mypy-strict-clean with no
   `type: ignore`, with identical runtime behavior to what the design describes.

Everything else matches the Design section as written: new module
`src/dander/pipeline/node_config.py` (`NodeType`, `NodeConfig`, `SourceNodeConfig`,
`TransformNodeConfig`, `TargetNodeConfig`, `_NODE_CONFIG_MODELS`, `resolve_node_config`); `Node`'s
`_route_config` `field_validator("config", mode="before")` routes via `info.data["type"]`;
`src/dander/pipeline/__init__.py` exports the five new symbols; `tests/pipeline/test_graph.py`'s
two modeled-node assertions now compare typed instances (plus one added `isinstance(..., dict)`
narrowing for mypy on the pre-existing mutable-default-container test, which still exercises an
unmodeled `task` node so behavior is unchanged); new `tests/pipeline/test_node_config.py` covers
per-type typed load (YAML + JSON), both-direction mismatch rejection (asserting no config values
leak), YAML/JSON round-trip across all three modeled types, backward compatibility (unmodeled
type, `params` alias, modeled-with-no-config, a DANDER-2-style graph), and `resolve_node_config`
directly (dict→typed, correct-instance passthrough, wrong-instance rejection, unmodeled-passthrough,
`None`/absent handling).

Toolchain: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` (strict, 35 files) all
clean; `uv run pytest` — 110 passed, 0 failed, no network. (One pre-existing, unrelated
`ruff check` failure in `scripts/watch_workflows.py`, a long line, predates this change and is out
of scope — confirmed via `git stash`.)

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed the implementation against all acceptance criteria and steering. Verdict: **PASS**.

**Acceptance criteria — all met:**

1. Per-node-type models present in `src/dander/pipeline/node_config.py`: `NodeConfig` base plus
   distinct `SourceNodeConfig`/`TransformNodeConfig`/`TargetNodeConfig`, discriminated by
   `Node.type` through the `_route_config` `field_validator("config", mode="before")` and the pure
   `resolve_node_config` seam. Fully type-annotated; mypy strict clean (35 files).
2. Boundary validation: a wrong typed-config instance is rejected with a clear `ValidationError`
   naming both class names and the node type. Verified by direct repro that no config value leaks
   into the exception string (`hide_input_in_errors=True` on `Node`). The AC #2 raw-dict caveat is
   explicitly flagged in the Design (placeholder models carry no distinguishing fields yet, so
   raw-dict shape rejection is owned by DANDER-11/16 and out of scope per AC #8) — accepted as a
   documented, internally-consistent scope reading, not a gap.
3. Backward compatibility: unmodeled `task` keeps a free-form `dict` config (union annotated
   dict-first with `union_mode="left_to_right"` so smart-mode coercion can't silently absorb it);
   the `config`/`params` alias is preserved. Covered by tests.
4. Round-trips stably through both YAML and JSON via the existing load/dump functions; model
   equality asserted in `test_node_config.py` and the updated `test_graph.py`.
5. Google-style docstrings on every new public symbol; no secret values in configs, defaults, or
   fixtures. Diff scanned for credential-shaped literals — none (the `secret_table`/`/secret`
   strings are deliberate no-leak assertions, not real secrets).
6. `tests/pipeline/test_node_config.py` covers per-type typed load (YAML+JSON), both-direction
   mismatch rejection with no-leak assertions, round-trip stability in both formats, backward
   compat (unmodeled type, `params` alias, modeled-with-no-config, DANDER-2-style graph), and
   `resolve_node_config` directly. No network.
7. Toolchain green: `ruff check` + `ruff format --check` clean on the changed files, `mypy` clean
   (35 files), `uv run pytest` — 110 passed.
8. No scope creep in the code (shape + validation + serialization + tests only). Note: the diff
   also touches `CLAUDE.md` and adds `.claude/workflows/build.js` — orchestration tooling unrelated
   to this ticket, not a steering violation and not part of the reviewed code surface.

Security: no hardcoded secrets, no PII/secret values in logs, fixtures, or error messages; the
mismatch error is repr-suppressed. Design fidelity: matches the approved Design with the three
documented Pydantic-runtime deviations (union order/`left_to_right`, `hide_input_in_errors`,
`_NODE_CONFIG_MODELS` typed `dict[str, ...]` for mypy-strict), all sound.
