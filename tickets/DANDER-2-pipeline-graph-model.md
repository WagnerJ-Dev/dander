---
id: DANDER-2
title: Pydantic pipeline-graph models (Node/Edge/PipelineGraph) with YAML/JSON round-trip
status: done
component: python
epic: pipeline
depends_on: []
created: 2026-07-21
---

## Context

Dander's orchestration layer needs a durable, declarative "pipeline graph" primitive: the graph of
data objects/tasks (nodes) and how they connect (edges). It is the storage format behind a future
drag-drop UI *and* the format people author programmatically with no UI at all. This ticket
establishes the new in-scope Python package `src/dander/pipeline/` and its core data model +
serialization. Graph **validation and algorithms** (uniqueness, dangling edges, self-loops, DAG /
cycle detection, adjacency, topological order) are split into DANDER-3, which builds on these
models — keep this ticket to the model shape and stable serialization only.

**Decided format (not up for re-litigation):** the stored YAML/JSON has a top-level `nodes:` list
and a top-level `edges:` list. Each edge is `{from, to, metadata}`. In/out adjacency is **derived**
downstream (DANDER-3), never stored twice. Python gotcha: `from` is a reserved keyword, so the
`Edge` model must expose the YAML/JSON keys `from`/`to` via Pydantic **field aliases** while using
Python-safe attribute names (e.g. `source`/`target` or `from_`/`to_`).

This is Python-only. No frontend/JS is in scope here (see `steering/00-project-overview.md`
non-goals). The baseline is green and must stay green.

## Acceptance Criteria

- [ ] New package `src/dander/pipeline/` exists with an `__init__.py` and a module holding the
      models; the module has a module-level docstring stating its responsibility.
- [ ] Pydantic v2 `Node` model with fields: `id` (unique string identifier), `type` (e.g.
      source/transform/target/task), `name`, and a free-form node-specific data dict
      (`config`/`params`, defaulting to empty). Fully type-annotated.
- [ ] Pydantic v2 `Edge` model with `from`/`to` **YAML/JSON keys exposed via field aliases** over
      Python-safe attribute names (never a literal `from` attribute), plus an optional `metadata`
      dict. Populating and serializing both work by alias.
- [ ] Pydantic v2 `PipelineGraph` model with `name`, `nodes: list[Node]`, and `edges: list[Edge]`.
- [ ] Load a graph from a **YAML** file and from a **JSON** file into `PipelineGraph`.
- [ ] Dump a `PipelineGraph` back to **YAML** and to **JSON** (edges serialize with `from`/`to`
      keys, matching the decided format).
- [ ] Round-trip is stable: load → dump → load yields an equivalent graph (assert model equality),
      for both YAML and JSON, including edges that carry `metadata` and nodes that carry
      `config`/`params`.
- [ ] No mutable default arguments; dict defaults use proper Pydantic default factories.
- [ ] Google-style docstrings on the public models and load/dump functions; fully type-annotated
      per `steering/languages/python.md`.
- [ ] pytest tests cover: a valid multi-node/multi-edge graph loads from YAML and from JSON; the
      `from`/`to` alias populates and serializes correctly (including the reserved-keyword case);
      and YAML and JSON round-trips are stable. Tests live under `tests/` and require no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations (no secrets, no sensitive sample data; style + docs per steering); no
      scope beyond the models + serialization and their tests (validation/algorithms are DANDER-3).

## Design

### Approach

This ticket introduces a new in-scope package `src/dander/pipeline/` holding **only** the
declarative data model and its serialization. It is a pure boundary-model concern: three Pydantic
v2 models (`Node`, `Edge`, `PipelineGraph`) plus four thin free functions for YAML/JSON load and
dump. There is deliberately no validation logic, no adjacency, no DAG/cycle work here — those are
DANDER-3, which imports these models. Keeping this ticket to "shape + stable serialization" is a
scope constraint from the ticket and `steering/00-project-overview.md`.

The models live in one module (`graph.py`) since they are a single cohesive concept (a graph and
its two element types), matching the "one concept per module" house rule in
`steering/languages/python.md` and mirroring the existing `dander.transform.model` pattern (Pydantic
boundary models in a domain-named module, free functions alongside). Unlike `transform.model`,
which uses `@dataclass` for internal value objects, these are external-payload / config models that
round-trip to disk, so **Pydantic v2 is the correct tool** per the steering rule "Pydantic v2 models
for all config objects and external payloads (validation at the boundary)."

**The `from`/`to` reserved-keyword problem** is the one real design decision. `Edge` stores
Python-safe attribute names `source` and `target` and maps them to the on-disk keys `from`/`to`
via Pydantic v2 field aliases. To make *both* populate-by-alias and dump-by-alias work cleanly we
configure the model with `populate_by_name=True` and `serialize_by_alias=True` (Pydantic 2.11+),
and always dump with `by_alias=True` in the dump functions as the belt-and-suspenders guarantee.
Chosen attribute names: `source`/`target` (reads clearly as a directed edge; avoids trailing-
underscore noise of `from_`/`to_`). The ticket explicitly permits either — this picks one.

**Serialization functions** are kept as module-level free functions (not methods on
`PipelineGraph`) so the model stays a pure data object and the I/O side effects live at the edges
(steering: "push side effects to the edges"). YAML uses `yaml.safe_load` / `yaml.safe_dump`
(the `pyyaml` dep is already pinned; `types-pyyaml` is already in dev deps for mypy). JSON uses
Pydantic's own `model_dump_json` / `model_validate_json` for load/dump to avoid a hand-rolled
`json` layer and to get alias handling for free. YAML goes through `model_dump(by_alias=True,
mode="json")` → `yaml.safe_dump`, and `yaml.safe_load` → `model_validate` on the way back.

**Round-trip stability** falls out of two things: (1) alias symmetry (dump-by-alias emits
`from`/`to`, load-by-alias/name accepts them), and (2) Pydantic model equality — two
`PipelineGraph` instances are `==` when all fields including nested lists are equal, so tests assert
`loaded == reloaded`. Default factories (`dict`, `list`) ensure `config`/`params`/`metadata`/`nodes`/
`edges` default to fresh empty containers with **no mutable default args**.

### Interfaces / classes

Module `src/dander/pipeline/graph.py`:

- **`Node(BaseModel)`** — a graph node.
  - `id: str` — unique identifier (uniqueness is *not* enforced here; that's DANDER-3).
  - `type: str` — node kind, e.g. `source`/`transform`/`target`/`task` (free string, not an enum —
    the ticket lists these as examples, not a closed set; keeping it open avoids blocking custom
    node types and is honest about validation being deferred to DANDER-3).
  - `name: str` — human label.
  - `config: dict[str, Any] = Field(default_factory=dict)` — free-form node-specific data. The
    ticket names this `config`/`params`; expose `config` as the canonical attribute and accept
    `params` as a **validation alias** so either key loads, with `populate_by_name=True` letting the
    attribute name also work. (If the Code agent finds this alias adds friction, a single `config`
    field satisfies the AC literally — see Open question.)
  - `model_config = ConfigDict(populate_by_name=True)`.

- **`Edge(BaseModel)`** — a directed connection between two node ids.
  - `source: str = Field(alias="from")`, `target: str = Field(alias="to")` — Python-safe attrs,
    on-disk keys `from`/`to`. Never a literal `from` attribute.
  - `metadata: dict[str, Any] = Field(default_factory=dict)` — optional edge metadata.
  - `model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)` so construction
    works by attribute name *and* by alias, and serialization emits the aliases.

- **`PipelineGraph(BaseModel)`** — the whole graph.
  - `name: str`.
  - `nodes: list[Node] = Field(default_factory=list)`.
  - `edges: list[Edge] = Field(default_factory=list)`.
  - `model_config = ConfigDict(populate_by_name=True)`.

Module-level free functions (all fully typed, Google-style docstrings):

- **`load_graph_from_yaml(path: Path) -> PipelineGraph`** — read + `yaml.safe_load` +
  `PipelineGraph.model_validate`.
- **`load_graph_from_json(path: Path) -> PipelineGraph`** — read +
  `PipelineGraph.model_validate_json`.
- **`dump_graph_to_yaml(graph: PipelineGraph, path: Path) -> None`** —
  `graph.model_dump(by_alias=True, mode="json")` → `yaml.safe_dump` → write.
- **`dump_graph_to_json(graph: PipelineGraph, path: Path, *, indent: int = 2) -> None`** —
  `graph.model_dump_json(by_alias=True, indent=indent)` → write.

Consider string-oriented siblings only if trivial (e.g. keep the dump helpers writing to `Path`);
do **not** add speculative overloads. All four take/return `Path` to keep I/O explicit.

### Files to touch / create

- **`src/dander/pipeline/__init__.py`** (new) — module docstring stating the package's
  responsibility (declarative pipeline-graph model + serialization; validation/algorithms are
  DANDER-3). Match the existing docstring-only `__init__.py` convention (e.g.
  `transform/__init__.py`); optionally re-export the three models + four functions for ergonomics
  (`from .graph import ...`) — low risk, improves the import surface.
- **`src/dander/pipeline/graph.py`** (new) — module docstring + the three models + four
  load/dump functions. `from __future__ import annotations` at top, matching every other module.
- **`tests/pipeline/__init__.py`** (new, if the existing `tests/transform/` package layout implies
  packages) — check whether `tests/transform/` has an `__init__.py`; mirror whatever the baseline
  does (it currently does not appear to, so likely no `__init__.py` needed — follow the baseline).
- **`tests/pipeline/test_graph.py`** (new) — the pytest suite (see Test seams). Uses `tmp_path`
  for file round-trips; **no network**, no committed sensitive data (use obviously-fake node ids
  like `n1`/`extract_users`, per `steering/01-security.md`).

No changes to `pyproject.toml` needed: `pydantic`, `pyyaml` are runtime deps; `types-pyyaml`,
`pytest` are dev deps already present.

### Test seams (what gets unit-tested, what gets mocked)

Nothing external to mock — this is pure model + local file I/O, exercised through `tmp_path`.
Cover:
1. A valid multi-node/multi-edge graph loads from a YAML file and from a JSON file (build the file
   contents inline in the test with `from`/`to` keys and `config`/`metadata` populated).
2. Alias behavior: constructing `Edge` by alias (`Edge(**{"from": "a", "to": "b"})`) and by attr
   name (`Edge(source="a", target="b")`) both work; `model_dump(by_alias=True)` emits `from`/`to`
   (assert the reserved-keyword key is present and no `source`/`target` keys leak).
3. Stable round-trip for **both** formats: `dump → load → dump → load` and assert the two
   `PipelineGraph` instances are `==`, including edges carrying `metadata` and nodes carrying
   `config`/`params`.
4. Defaults: a `Node`/`Edge` built without `config`/`metadata` yields independent empty dicts
   (mutate one instance's dict, assert another instance's is untouched) — guards the
   default-factory requirement.

### Trade-offs

- **Free string `type` vs. `StrEnum`.** `transform.model` uses a `StrEnum` for materialization.
  Here the ticket gives node types as *examples* and defers validation to DANDER-3, so a closed
  enum would over-constrain and pull validation into this ticket. Chose free `str`; DANDER-3 can
  layer an accepted-values check.
- **`model_dump_json` for JSON vs. stdlib `json`.** Using Pydantic's JSON methods keeps alias/type
  handling in one place and avoids a second serialization code path that could drift from YAML.
- **Free functions vs. `PipelineGraph.save()/load()` methods.** Free functions keep the model a
  pure value object and localize I/O, per steering. Slightly less discoverable; re-exporting from
  `__init__` mitigates that.
- **`params` alias on `Node.config`.** The AC says the field is "`config`/`params`". Supporting
  both via alias is friendlier but adds a small amount of config surface. Acceptable and reversible.

### Open question / flag for Code + Review

- The AC phrase **"free-form node-specific data dict (`config`/`params`)"** is ambiguous: is it one
  field with two accepted names, or literally either name is fine? This design reads it as one
  canonical `config` field with `params` accepted as an alias. If Review prefers strictly one name,
  drop the alias and keep `config` — both satisfy the literal AC. Called out so it's a conscious
  choice, not a silent guess.

## Implementation Notes

Implemented exactly per Design, no scope deviations.

- **New files:**
  - `src/dander/pipeline/graph.py` — `Node`, `Edge`, `PipelineGraph` (Pydantic v2) +
    `load_graph_from_yaml`/`load_graph_from_json`/`dump_graph_to_yaml`/`dump_graph_to_json`.
  - `src/dander/pipeline/__init__.py` — module docstring + re-exports of the three models and
    four functions.
  - `tests/pipeline/test_graph.py` — 10 pytest cases (no `__init__.py`, matching the
    `tests/transform/` baseline convention of no package `__init__.py` under `tests/`).
- **`Edge`** uses attribute names `source`/`target` with `Field(alias="from" / "to")`,
  `model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)`, and dump functions
  additionally pass `by_alias=True` (belt-and-suspenders per Design). Verified by test that dumped
  output contains `from`/`to` keys and never `source`/`target`.
- **`Node.config`** resolved the Design's flagged open question: implemented as one canonical
  `config` attribute accepting `AliasChoices("config", "params")` as `validation_alias`, so either
  on-disk key populates it, and it always serializes back out as `config`. Chosen over a stricter
  single-name-only field because it satisfies the AC's literal `config`/`params` phrasing without
  ambiguity for callers using either convention.
- **JSON (de)serialization** uses Pydantic's own `model_validate_json`/`model_dump_json` (with
  `by_alias=True`); **YAML** goes through `model_dump(by_alias=True, mode="json")` →
  `yaml.safe_dump(sort_keys=False)` and `yaml.safe_load` → `model_validate`, as specified.
- **Deviation from the toolchain baseline (flagging for Review):** mypy strict flagged
  `Edge(source=..., target=...)` (attribute-name construction) as `[call-arg]` even with
  `populate_by_name=True`, because mypy's built-in PEP 681 `dataclass_transform` support (which
  pydantic's `ModelMetaclass` uses) only recognizes the field's `alias` as the synthesized
  `__init__` parameter name unless the dedicated `pydantic.mypy` plugin is active. Added
  `plugins = ["pydantic.mypy"]` to `[tool.mypy]` in `pyproject.toml` — this is pydantic's own
  documented fix for exactly this gap and does not change type-checking behavior for the existing
  `@dataclass`-based `transform.model` code. Re-ran full `mypy` after the change: no new issues in
  any of the other 25 source files.
- **Tooling results (repo-wide, not just this ticket's files):**
  - `uv run ruff check .` — All checks passed.
  - `uv run ruff format --check .` — 26 files already formatted.
  - `uv run mypy` — Success: no issues found in 26 source files.
  - `uv run pytest` — 26 passed (10 new in `tests/pipeline/test_graph.py`, 16 pre-existing).

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-21 — PASS

Reviewed implementation (`src/dander/pipeline/graph.py`, `src/dander/pipeline/__init__.py`,
`tests/pipeline/test_graph.py`, plus the one-line `pyproject.toml` mypy-plugin change) against all
acceptance criteria and steering (`01-security.md`, `02-engineering.md`, `languages/python.md`).

Acceptance criteria — all met:
- New `src/dander/pipeline/` package with docstring-carrying `__init__.py` and `graph.py`; both have
  module-level docstrings stating responsibility and scoping validation/algorithms out to DANDER-3.
- `Node` (id/type/name/config) fully annotated; `config` defaults via `default_factory=dict` and
  accepts `config`/`params` via `AliasChoices`, dumps under canonical `config`.
- `Edge` uses Python-safe `source`/`target` with `Field(alias="from"/"to")`; never a literal `from`
  attribute; `populate_by_name=True` + `serialize_by_alias=True`; populate- and dump-by-alias both
  verified.
- `PipelineGraph` (name/nodes/edges) with list default factories.
- YAML and JSON load/dump free functions present; edges serialize with `from`/`to` (tests assert the
  reserved-keyword keys are emitted and `source`/`target` never leak).
- Round-trip stability asserted via model equality for both YAML and JSON, including edge `metadata`
  and node `config`.
- No mutable default args (independent-empty-container test guards this); Google-style docstrings on
  all public models and functions; fully type-annotated.
- 10 new pytest cases, no network (uses `tmp_path`), fake node ids only.

Toolchain re-run independently and confirmed green: `uv run ruff check .` (all passed),
`uv run ruff format --check .` (26 files formatted), `uv run mypy` (no issues, 26 source files),
`uv run pytest` (26 passed; 10 new in `tests/pipeline/`).

Security: no hardcoded secrets, no PII/sensitive sample data, no secrets in logs — clean.

Scope/deviation: the `plugins = ["pydantic.mypy"]` addition to `pyproject.toml` is outside the
"no pyproject changes needed" design note, but it is explicitly flagged in Implementation Notes,
is pydantic's own documented fix for the mypy PEP 681 `populate_by_name` false positive, leaves all
26 source files passing mypy strict, and introduces no runtime/behavior change. Justified and
non-blocking. No scope creep into DANDER-3 validation/algorithms.

Verdict: PASS.
