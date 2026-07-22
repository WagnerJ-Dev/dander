---
id: DANDER-3
title: Pipeline-graph validation + derived adjacency and topological order
status: done
component: python
epic: pipeline
depends_on: [DANDER-2]
created: 2026-07-21
---

## Context

Building on the pipeline-graph models from DANDER-2, this ticket adds the correctness layer that
makes a `PipelineGraph` safe to hand to the orchestration layer: structural **validation** with a
clear typed error hierarchy, and the **derived** graph helpers (adjacency + execution ordering).
Adjacency is computed from the stored `edges` list — never stored twice (see the decided format in
DANDER-2 and `steering/00-project-overview.md`).

Because a pipeline graph drives execution order, an invalid graph (dangling edge, self-loop, cycle,
duplicate id) must fail **loud and actionable**, naming the offending element — per
`steering/02-engineering.md` ("fail loud with actionable context"). This ticket is Python-only and
depends on DANDER-2's models existing.

## Acceptance Criteria

- [ ] A typed error hierarchy rooted at a `GraphValidationError` (e.g. subclasses for duplicate id,
      dangling edge, self-loop, cycle). Each error message **names the offending element(s)** (the
      duplicate id, the edge and the missing node id, the self-loop node, or the cycle path).
- [ ] A validation entrypoint on/for `PipelineGraph` that checks, and raises the right typed error
      for each failure:
      - node ids are unique (duplicate id → error naming the id);
      - every edge `from`/`to` references an existing node id (dangling edge → error naming the
        edge and the unknown id);
      - no self-loops (an edge from a node to itself → error naming the node);
      - the graph is a DAG (cycle detected → error reporting the **cycle path**).
- [ ] Derived helpers: predecessors/successors (or `in_edges`/`out_edges`) for a given node id,
      computed from the `edges` list (not stored separately).
- [ ] `topological_order()` returns node ids (or nodes) in a valid execution order for a DAG;
      calling it on a graph with a cycle raises the cycle error (or requires validation first with a
      documented, tested contract).
- [ ] A valid graph passes validation with no error raised.
- [ ] Google-style docstrings on the public validation/helper APIs and the error classes; fully
      type-annotated per `steering/languages/python.md`. Errors are explicit with context and never
      include secrets or sensitive data.
- [ ] pytest tests cover: a valid graph validates cleanly; each failure mode (duplicate id, dangling
      edge, self-loop, cycle) raises the **correct** typed error with a helpful message that names
      the offending element / reports the cycle path; predecessors/successors are correct for a
      known graph; and `topological_order()` returns a correct ordering (every edge goes earlier →
      later). Tests live under `tests/` and require no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond validation + derived helpers + topological order and
      their tests. The stored format is unchanged (adjacency stays derived, not persisted).

## Design

### Approach

DANDER-2 gives us pure Pydantic data models (`Node`, `Edge`, `PipelineGraph`) that only describe
*shape* and serialization. DANDER-3 adds the *correctness layer* as a set of pure, side-effect-free
operations that take a `PipelineGraph` and either return derived data or raise a typed error. We keep
these operations **out of the model module** so the model stays a pure value object (SRP) and so we
avoid an import cycle: algorithms depend on the model, never the reverse (DIP). This also honours the
scope rule "stored format unchanged / adjacency stays derived" — nothing here is persisted onto the
model, and DANDER-2's module is not modified.

The public surface is small and functional: a `validate(graph)` entrypoint, a `topological_order(graph)`
function, and a derived `AdjacencyIndex` value object that computes predecessors/successors **once**
from the `edges` list and is reused by validation, ordering, and the neighbour-lookup helpers. Adjacency
is therefore computed, never stored twice.

Validation runs its checks in a **fixed order** so each later check can assume the earlier invariants
hold: (1) duplicate node ids, (2) dangling edges (endpoint not a known node id), (3) self-loops, (4)
cycle / DAG check. Duplicate ids come first because everything downstream keys adjacency by id and a
duplicate makes that ambiguous; dangling edges come before adjacency-based checks because we can't build
a coherent index over unknown ids; self-loops are reported distinctly before the general cycle detector
so an edge `x → x` yields a `SelfLoopError` (naming `x`) rather than a length-1 `GraphCycleError`.

Cycle detection uses **DFS with three-colour marking** (white/grey/black) while carrying the current
recursion stack. When DFS reaches a grey (in-progress) node we slice the stack from that node to the
current node to produce the **cycle path**, which the `GraphCycleError` reports. DFS is chosen over Kahn's
algorithm specifically because the ticket requires the offending cycle *path* — Kahn detects "a cycle
exists" cheaply but recovering the actual path needs a second pass. Nodes and neighbours are visited in
**insertion order** (order of the `nodes`/`edges` lists) so both `topological_order()` output and the
reported cycle path are deterministic and unit-testable.

`topological_order(graph)` calls `validate(graph)` first, so calling it on a cyclic (or otherwise
invalid) graph raises the corresponding typed error — a simple, safe, documented contract. The redundant
re-validation cost is negligible for these small author-time graphs; we do not add a speculative
`assume_valid` flag (no ticket asks for it).

### Interfaces / classes

**`src/dander/pipeline/errors.py`** — typed error hierarchy, each error stores the offending element(s)
and renders a message naming them (no secrets/PII — graph structure only):

- `GraphValidationError(Exception)` — root; catch-all for any structural failure.
- `DuplicateNodeIdError(GraphValidationError)` — `__init__(self, node_id: str)`; message names the id.
- `DanglingEdgeError(GraphValidationError)` — `__init__(self, *, source: str, target: str, missing_id: str)`;
  message names the edge (`from`→`to`) and the missing endpoint id.
- `SelfLoopError(GraphValidationError)` — `__init__(self, node_id: str)`; message names the node.
- `GraphCycleError(GraphValidationError)` — `__init__(self, cycle: list[str])`; stores the cycle path and
  renders it (documented form: the nodes in visitation order with the start node repeated at the end to
  close the loop, e.g. `a -> b -> c -> a`). Expose the raw path as a `cycle` attribute for tests.

**`src/dander/pipeline/graph_ops.py`** — derived structure + algorithms (pure functions):

- `@dataclass(frozen=True) class AdjacencyIndex` — derived index; private `_successors`/`_predecessors`
  maps of `dict[str, list[str]]` keyed by node id (values in edge-insertion order).
  - `classmethod from_graph(cls, graph: PipelineGraph) -> AdjacencyIndex` — build from `graph.edges`;
    assumes ids already validated (built after the duplicate/dangling checks pass, or for internal use
    where callers guarantee it — documented).
  - `successors(self, node_id: str) -> list[str]` / `predecessors(self, node_id: str) -> list[str]` —
    neighbour ids for a node (empty list if none; `KeyError`-free for known ids).
- `validate(graph: PipelineGraph) -> None` — the entrypoint; runs the four checks in the order above and
  raises the matching typed error, or returns `None` on a valid graph.
- `topological_order(graph: PipelineGraph) -> list[str]` — validates, then returns node ids in a valid
  execution order (every edge points from an earlier to a later id). Raises `GraphCycleError` (via
  `validate`) on a cyclic graph.

Optional convenience (only if trivially clean): module-level `predecessors(graph, node_id)` /
`successors(graph, node_id)` wrappers that build an `AdjacencyIndex` internally — but `AdjacencyIndex`
is the primary reusable API so callers doing many lookups don't rebuild it per call.

### Files to touch / create

- **create** `src/dander/pipeline/errors.py` — the error hierarchy above; module docstring stating its
  responsibility.
- **create** `src/dander/pipeline/graph_ops.py` — `AdjacencyIndex`, `validate`, `topological_order`;
  imports `PipelineGraph`/`Edge` from DANDER-2's model module under a `TYPE_CHECKING` guard where used
  only in annotations (ruff `TCH`); `from __future__ import annotations` at top (matches repo style).
- **edit** `src/dander/pipeline/__init__.py` — re-export the public names (errors, `validate`,
  `topological_order`, `AdjacencyIndex`) so `from dander.pipeline import validate, GraphCycleError, …`
  works.
- **create** `tests/pipeline/__init__.py` (if the tests dir needs it) and `tests/pipeline/test_graph_ops.py`
  — see test seams.

### Test seams

Everything here is pure and in-memory, so **no mocking and no network** — build small `PipelineGraph`
fixtures directly in the test. Cover:
- valid multi-node/multi-edge graph → `validate` returns `None` (no raise).
- each failure mode raises the **correct** type and the message names the offending element:
  duplicate id → `DuplicateNodeIdError` (asserts the id in the message); unknown endpoint →
  `DanglingEdgeError` (asserts edge + missing id); `x → x` → `SelfLoopError` (asserts node); cyclic
  graph → `GraphCycleError` (assert the `.cycle` path is the actual cycle, e.g. contains the offending
  nodes closing the loop).
- `AdjacencyIndex.successors`/`predecessors` return the exact expected neighbour ids for a known graph
  (including a node with none).
- `topological_order()` returns an ordering satisfying the invariant: for every edge, index(source) <
  index(target) — assert positionally, not against a hardcoded list, so a valid but differently-ordered
  result still passes. Also assert it raises `GraphCycleError` on a cyclic graph.

### Trade-offs

- **Module functions vs. methods on `PipelineGraph`.** Chose free functions in the pipeline package.
  Keeps the DANDER-2 model pure, avoids an import cycle (model ⇄ algorithms), and keeps the stored
  format untouched per scope discipline. A thin delegating `PipelineGraph.validate()` could be added
  later, but is deliberately not built here.
- **DFS three-colour vs. Kahn's algorithm.** DFS chosen so we can reconstruct and report the cycle path
  the acceptance criteria demand; Kahn would need a second traversal to recover it.
- **`AdjacencyIndex` computed once vs. recomputing per lookup.** A derived, frozen index is a single
  source of truth reused by validation, ordering, and neighbour lookups, and keeps adjacency *derived*
  (never persisted), matching the decided format.
- **`topological_order` self-validates.** Simplest safe contract; the tiny re-check cost is acceptable
  for author-time graphs and avoids a foot-gun where callers order an unvalidated graph.

### Notes / flags for the Code agent

- **Depends on DANDER-2, which is not yet implemented.** The exact model **module name** (e.g.
  `graph.py` vs `models.py`) and the **`Edge` Python attribute names** for the `from`/`to` aliases
  (DANDER-2's ticket floats `source`/`target` *or* `from_`/`to_`) are not yet fixed. This design writes
  edge endpoints as `source`/`target` for readability — **align these imports and attribute accesses
  with whatever DANDER-2 actually ships**; that is the only coupling point.
- Error messages must contain **graph structure only** (ids, edges) — never node `config`/`params`
  values, which per DANDER-2 are free-form and could carry sensitive data.

## Implementation Notes

Implemented exactly per Design, no scope deviations. DANDER-2 was already implemented (`done`) at
the time of this ticket, using attribute names `source`/`target` for `Edge` (matching the Design's
assumption exactly, so no import/attribute alignment was needed).

- **New files:**
  - `src/dander/pipeline/errors.py` — `GraphValidationError` root + `DuplicateNodeIdError`,
    `DanglingEdgeError`, `SelfLoopError`, `GraphCycleError`, each storing the offending
    element(s) as attributes and rendering a message that names them. Messages are
    structure-only (ids/edges), never node `config`/edge `metadata` values, per
    `steering/01-security.md`.
  - `src/dander/pipeline/graph_ops.py` — `AdjacencyIndex` (frozen dataclass; `from_graph`,
    `successors`, `predecessors`, each lookup returning a fresh copy so callers can't mutate
    internal state), `validate(graph)` (runs the four checks in the fixed order the Design
    specifies: duplicate ids → dangling edges → self-loops → acyclic/DAG), and
    `topological_order(graph)` (calls `validate` first, then a second DFS pass to produce the
    order). Cycle detection/topo-order share one internal `_dfs_topological_order` helper using
    three-colour (white/grey/black) DFS marking, visiting nodes/successors in insertion order for
    determinism; on hitting a grey node it slices the live recursion stack to build the reported
    cycle path.
  - `tests/pipeline/test_graph_ops.py` — 9 pytest cases (no `__init__.py`, matching the
    `tests/pipeline/test_graph.py` / `tests/transform/` baseline convention of no package
    `__init__.py` under `tests/`).
- **Edited** `src/dander/pipeline/__init__.py` — re-exports the five error types plus
  `AdjacencyIndex`, `validate`, `topological_order` alongside DANDER-2's existing exports; updated
  module docstring to point at `graph_ops` instead of saying validation is future work.
- **`PipelineGraph.validate()` method** — not added (per Design's stated trade-off): validation
  stays a free function in `graph_ops` to keep DANDER-2's model pure and avoid an import cycle;
  DANDER-2's module was not modified.
- **Tooling results** (repo-wide):
  - `uv run ruff check .` — All checks passed.
  - `uv run ruff format --check .` — 29 files already formatted.
  - `uv run mypy` — Success: no issues found in 29 source files.
  - `uv run pytest` — 35 passed (9 new in `tests/pipeline/test_graph_ops.py`, 26 pre-existing).

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-21 — PASS

Reviewed implementation (`src/dander/pipeline/errors.py`, `graph_ops.py`, `__init__.py`,
`tests/pipeline/test_graph_ops.py`) against all acceptance criteria and steering.

- **Acceptance criteria — all met.** Typed hierarchy rooted at `GraphValidationError` with
  `DuplicateNodeIdError`/`DanglingEdgeError`/`SelfLoopError`/`GraphCycleError`, each storing the
  offending element(s) as attributes and rendering a message that names them (cycle path rendered
  as `a -> b -> c -> a`). `validate()` runs the four checks in the correct fixed order
  (duplicate → dangling → self-loop → acyclic), so a self-loop yields `SelfLoopError` rather than a
  length-1 cycle. `AdjacencyIndex` derives predecessors/successors from `edges` only (never stored
  on the model) and returns fresh copies so callers can't corrupt internal state.
  `topological_order()` self-validates then returns a DFS order; verified the ordering invariant
  and cyclic-graph raise behavior.
- **Cycle path correctness verified** by trace: on hitting a grey node, `stack_path[index:]` +
  the grey node yields `[start, …, current, start]` — a real, closable cycle for both root and
  non-root cycles.
- **Security — clean.** No secrets/credential literals anywhere; error messages carry graph
  structure (ids/edges) only, never node `config` or edge `metadata` (per `01-security.md`).
- **Design fidelity — faithful.** Free functions kept out of the DANDER-2 model module (no import
  cycle, stored format untouched, `graph.py` unmodified); DFS three-colour marking with
  insertion-order determinism, exactly as designed. `PipelineGraph.validate()` method correctly
  omitted per the stated trade-off.
- **Conventions & tooling — green** (verified locally, repo-wide): `ruff check` all passed,
  `ruff format --check` 29 files formatted, `mypy` strict success on 29 files, `pytest` 35 passed
  (9 new in `tests/pipeline/test_graph_ops.py`). Full Google-style docstrings and complete type
  annotations throughout.
- **Scope — respected.** Only validation + derived helpers + topological order and their tests;
  adjacency stays derived. (Note: the working tree also carries an unrelated `pyproject.toml`
  mypy-plugin line and `scripts/watch_workflows.py` — not claimed by this ticket and not part of
  this diff's concern.)

No blocking issues. Status set to `done`.
