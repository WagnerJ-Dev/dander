---
id: DANDER-9
title: Document the pipeline-graph field, mapping, transformation, and join model
status: done
component: docs
epic: pipeline
depends_on: [DANDER-8]
created: 2026-07-22
---

## Context

DANDER-4–8 turn the pipeline graph from an opaque node/edge structure into a field-aware model:
nodes declare fields, connections map fields, transform them, and join sources — with a validation
layer to keep it honest. That is a meaningfully larger surface than DANDER-2/3 documented, and per
`steering/languages/python.md` ("READMEs per top-level package explaining its role") and the
CLAUDE.md docs role, the `pipeline` package needs a single, accurate reference so authors (and the
future drag-drop UI) know the on-disk format and the validation contract.

This ticket is documentation only: it must describe **exactly** what the shipped code does (no
aspirational features) and stay true to the final field/edge keys, transformation kinds, join types,
and error types. It carries no secrets or real sample data — examples use obviously-fake node/field
names (`steering/01-security.md`).

## Acceptance Criteria

- [ ] A README (or equivalent package doc) for `src/dander/pipeline/` that explains: the node
      **field schema**, the connection **field-to-field mapping**, connection **transformations**
      (kinds and that expressions are evaluated downstream, not here), the **join specification**,
      and the **validation** layer (structural + field-wiring) with the typed errors it raises.
- [ ] An annotated end-to-end YAML example showing a source node with fields, a connection with
      mappings, a transformation, and a join — using only fake, non-sensitive names/values — that is
      consistent with the shipped models (a reader could author a valid graph from it).
- [ ] Documents how the example maps to the JSON form and notes the `from`/`to` (and any other
      alias) on-disk keys so both serializations are covered.
- [ ] Cross-links the relevant tickets/steering and states the scope boundary: the graph is
      declarative; execution (expression evaluation, join/SQL generation, ingestion) lives in the
      Transform/Ingestion/Writer layers per `steering/00-project-overview.md`.
- [ ] Docs are accurate to the code as merged (field/edge keys, transformation kinds, join types,
      error class names all match); no secrets or real/sensitive sample data. If a real product
      decision was made along the way (e.g. joins on the graph, per DANDER-7), it is reflected and
      pointed at the Decision Log.

## Design

### Approach

This is a **documentation-only** ticket: no Python, no models, no tests. The deliverable is one new
Markdown file, `src/dander/pipeline/README.md`, satisfying the `steering/languages/python.md` rule
"READMEs per top-level package explaining its role and how it plugs into the module map." It is the
first package README in `src/dander/` — there is no existing one to match, so this doc also sets the
house pattern for the rest.

The single hard constraint dominates every other decision: **the README must describe exactly what
the merged code does, not what these tickets aspire to.** DANDER-9 `depends_on: [DANDER-8]`, and in
the `feature` workflow the Build stage runs serially, so by the time this ticket is coded,
DANDER-4–8 will have shipped. Their *ticket text* is the intent; the *merged source* is the truth.
The design below lists the expected shapes as a documentation checklist, but the code agent's first
action is to **re-read the merged pipeline package and document the real names, keys, kinds, types,
and error classes** — reconciling any drift (e.g. the field model shipping as `NodeField` vs
`FieldSpec`, or the actual set of transformation `kind` values) in favor of the code. Where a
detail in this design contradicts merged code, the code wins and the discrepancy is worth a one-line
note in Implementation Notes.

Ground the doc in the source of truth, which at design time already includes DANDER-2/3 and will
include DANDER-4–8:
- `src/dander/pipeline/graph.py` — `Node`, `Edge`, `PipelineGraph`, load/dump for YAML+JSON. Note
  the two already-shipped alias facts the README must state precisely: `Edge` exposes Python
  attributes `source`/`target` but the **on-disk keys are `from`/`to`** (Pydantic
  `serialize_by_alias`, dumps always emit `from`/`to`); and `Node.config` accepts **either `config`
  or `params`** on load (`AliasChoices`) but dumps canonically as `config`. These are exactly the
  "`from`/`to` (and any other alias) on-disk keys" the acceptance criteria call for.
- `src/dander/pipeline/graph_ops.py` — `validate`, `topological_order`, `AdjacencyIndex` (structural
  layer). Plus whatever field-wiring validation DANDER-8 adds here or in a documented companion.
- `src/dander/pipeline/errors.py` — the `GraphValidationError` hierarchy (`DuplicateNodeIdError`,
  `DanglingEdgeError`, `SelfLoopError`, `GraphCycleError`) plus DANDER-8's new field-wiring errors.
- `src/dander/pipeline/__init__.py` `__all__` — the public surface the README should treat as the
  supported API; document what's exported, not internal helpers.

### Document structure (README sections)

1. **Role & module map link** — one paragraph: the pipeline package owns the *declarative* graph
   primitive behind both the future drag-drop UI and code-authored pipelines; point back to the
   module map in `steering/00-project-overview.md`.
2. **Node field schema** (DANDER-4) — the per-node field model and its keys: `name`, `type` (free
   string, BigQuery-ish, values not yet validated), `nullable` (+ its default), `description`, and
   the free-form `metadata` dict — stating explicitly that `metadata` holds **tags/labels only
   (e.g. sensitivity/PII), never a real value or sample data**. `Node.fields` is an ordered,
   default-empty collection; a fieldless node is unchanged from DANDER-2.
3. **Connection field-to-field mapping** (DANDER-5) — `FieldMapping`'s source-field and target-field
   references (both **field-name strings**), ordered `Edge.mappings`, optional `metadata`. State the
   exact on-disk key names for the source/target field references as merged, and that mappings
   reference fields **by name, never by value**.
4. **Connection transformations** (DANDER-6) — the transformation representation attached to a
   mapping/edge: its **kind** set (as merged — e.g. `direct`/`expression`/`constant`), the payload
   per kind (expression string / constant literal), the declared **input field references**, and the
   Pydantic boundary constraints (e.g. `expression` requires a non-empty expression). State loudly
   that **expressions are opaque, declarative strings evaluated downstream in Transform/Writer — not
   here** — and that they must never embed a secret/credential.
5. **Join specification** (DANDER-7) — the join model: the closed **join-type** set
   (inner/left/right/full) and the ordered **key-pair** collection (left field ↔ right field).
   Explicitly document **which endpoint is left vs. right relative to the edge's `from`/`to`
   direction** (per DANDER-7 AC), that a join is optional per edge, and that at least one key pair is
   required. No SQL is generated here.
6. **Validation layer** — two tiers, in the order they run: (a) **structural** (DANDER-3) —
   duplicate ids, dangling edges, self-loops, cycles, via `validate`/`topological_order`; (b)
   **field-wiring** (DANDER-8) — duplicate field name within a node, unknown field references from
   mappings/transformations/joins, join-key-not-on-joined-node — and the contract that **structural
   checks run first**. List each **typed error class by its real name** with its trigger; note all
   subclass `GraphValidationError` (catch-generically) and that messages carry **structure only (ids
   + field names), never `config`/`metadata`/transformation payloads/values**.
7. **Annotated end-to-end YAML example** — one graph using only obviously-fake names (e.g. a source
   node `crm_contacts` with fields `contact_id`, `full_name`; a connection to `warehouse_customers`
   with a direct mapping, an `expression` transformation, and a join on `contact_id ↔ customer_id`).
   Inline comments annotate each block. It must be **authorable-valid** against the merged models —
   the code agent should sanity-check it round-trips (`load_graph_from_yaml`) rather than hand-waving.
8. **JSON form & on-disk keys** — show (or describe) the same graph as JSON and enumerate the
   alias/on-disk keys so both serializations are covered: at minimum `from`/`to` for edges, the
   `config`/`params` load-alias for nodes, and the mapping source/target field keys as merged.
9. **Scope boundary** — the graph is **declarative**; execution (expression evaluation, join/SQL
   generation, ingestion, materialization) lives in the Transform/Ingestion/Writer layers per
   `steering/00-project-overview.md`. Cross-link DANDER-2–8 and the three relevant steering files.
10. **Decision Log pointer** — if the join-on-graph fork (DANDER-7's product flag) was taken, the
    README notes it and points at the Decision Log entry in `steering/00-project-overview.md`. The
    code agent must **check whether that Decision Log entry actually exists**; if DANDER-7 shipped,
    the entry should be there — if it's missing, flag it rather than inventing one.

### Files to touch

- **Create** `src/dander/pipeline/README.md` — the package reference described above. This is the
  only deliverable.
- **Do not** modify any `.py` file, model, or test. If, while grounding the doc, the code agent finds
  the code and a ticket genuinely disagree, that is a finding for Implementation Notes / a follow-up
  ticket — **not** something to fix under a docs ticket.

### Trade-offs

- **One README vs. split docs** — a single package README (not per-file docs) is what the steering
  rule and acceptance criteria ask for, and it keeps the field/mapping/transform/join/validation
  story in one authorable narrative. Chosen.
- **Prose + one worked example vs. exhaustive field tables** — lead with a single annotated
  end-to-end example (the AC's explicit requirement) and concise per-concept key lists, rather than a
  full reference table per model. The models' own Google-style docstrings remain the exhaustive
  field-level reference; the README is the orientation + on-disk-format layer that ties them together
  and avoids duplicating (and drifting from) docstrings.
- **Design-time intent vs. merge-time truth** — this design deliberately encodes *expected* shapes
  from DANDER-4–8's tickets while instructing the code agent to verify against merged source, because
  the models don't exist yet at design time. The alternative (waiting) isn't available in the
  workflow; the mitigation is the explicit "code wins, reconcile drift" rule above.

### Test seams

No unit tests are in scope (docs-only). The one mechanical verification worth doing: the code agent
should **load the README's YAML example through `load_graph_from_yaml` (and ideally
`validate`/field-wiring validation) in a throwaway check** to prove the example is authorable-valid
and internally consistent before finalizing — but this is a correctness check on the example, not a
committed test. CI's `ruff`/`mypy`/`pytest` are unaffected since no code changes.

### Flags / under-specified criteria

- The acceptance criteria and this design are only fully satisfiable **after DANDER-4–8 are merged**;
  documenting them earlier would violate the "no aspirational features" rule. This ordering is
  already encoded by `depends_on: [DANDER-8]` — noting it so the workflow doesn't schedule DANDER-9's
  code stage before its dependencies land.
- If DANDER-7 (joins) was **parked** rather than shipped (it carries an explicit product fork), the
  README must simply **omit the join section** and the code agent should note that joins are not part
  of the merged model — the rest of the doc (fields/mappings/transformations/validation) still stands.

## Implementation Notes

_Filled by the Documentation agent._

**What was built:** `src/dander/pipeline/README.md` — the package reference for
`dander.pipeline`, covering role, package layout, node field schema, connection field-to-field
mapping, transformations, join specification, the two-tier validation layer (with every typed
error listed by real class name), an annotated end-to-end YAML example, the equivalent JSON form
with an on-disk/alias-key table, the scope boundary, and cross-links to DANDER-2–8 and the three
universal steering files. No `.py` file was touched, per the ticket's "docs only" file scope.

**Grounding:** re-read the merged source directly (`graph.py`, `graph_ops.py`, `errors.py`,
`__init__.py`), not the design's projected shapes. All names/keys/kinds in the doc match the
merged code exactly: `NodeField`, `FieldMapping`, `Transformation`/`TransformationKind`
(`direct`/`expression`/`constant`), `JoinSpec`/`JoinKeyPair`/`JoinType`
(`inner`/`left`/`right`/`full`), and the error hierarchy (`DuplicateNodeIdError`,
`DanglingEdgeError`, `SelfLoopError`, `GraphCycleError`, `DuplicateFieldNameError`,
`UnknownFieldReferenceError`, `JoinKeyFieldError` as a subclass of `UnknownFieldReferenceError`).
No drift found between the design's projected shapes and the merged models (DANDER-7's join work
was not parked — it shipped — so the join section stands).

**Example verified mechanically (not a committed test):** wrote the README's YAML example to a
scratch file and ran it through `load_graph_from_yaml` + `validate_field_wiring` +
`dump_graph_to_yaml`/`load_graph_from_yaml` round-trip in a throwaway `uv run python` check — it
loads, validates clean, and round-trips byte-stable. The JSON form shown in the README is the
literal `dump_graph_to_json` output for that same graph (via `uv run` in the scratchpad), not
hand-typed.

**Deviations / findings worth flagging (not fixed here — docs-only ticket):**
1. **`dander.pipeline.__init__.py` does not export the field/mapping/transformation/join model
   classes.** `__all__` re-exports `Node`, `Edge`, `PipelineGraph`, the `load_*`/`dump_*`
   functions, the `graph_ops` functions, and the full `errors` hierarchy — but **not**
   `NodeField`, `FieldMapping`, `Transformation`, `TransformationKind`, `JoinSpec`, `JoinKeyPair`,
   or `JoinType`. All shipped tests (`tests/pipeline/test_graph*.py`,
   `test_transformations.py`, `test_field_validation.py`) import these directly from
   `dander.pipeline.graph`, confirming this is the real current surface, not an oversight in one
   test. The README documents the actual import paths (submodule import required for these
   classes) rather than papering over it, and calls this out explicitly in a "Import paths"
   subsection — but it is a plausible follow-up ticket (add them to `__all__` for API
   consistency with `Node`/`Edge`/`PipelineGraph`).
2. **No Decision Log entry for the join-on-graph product decision.** DANDER-7 shipped with an
   explicit "product flag" that the decision should be recorded in
   `steering/00-project-overview.md`'s Decision Log once made. Checked the Decision Log directly
   (`grep`'d for "join"/"pipeline") — no entry exists. Per the ticket design's explicit
   instruction ("flag it rather than inventing one"), the README's closing "Decision Log status"
   section states this gap plainly instead of fabricating an entry. Flagging here too so it's
   visible to PR-review / a follow-up ticket to actually append the entry.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-22 — PASS

Reviewed `src/dander/pipeline/README.md` against all five acceptance criteria and the three
universal steering files. Verdict: **PASS**.

**Accuracy (grounded against merged source, not the design's projected shapes):**
- Every name/key/kind/type/error in the doc matches the merged code exactly. Verified against
  `graph.py` (`NodeField`, `FieldMapping`, `Transformation`/`TransformationKind` =
  `direct`/`expression`/`constant`, `JoinSpec`/`JoinKeyPair`/`JoinType` =
  `inner`/`left`/`right`/`full`), `errors.py` (`DuplicateNodeIdError`, `DanglingEdgeError`,
  `SelfLoopError`, `GraphCycleError`, `DuplicateFieldNameError`, `UnknownFieldReferenceError`,
  `JoinKeyFieldError` as a subclass of `UnknownFieldReferenceError`), and `graph_ops.py`
  (`validate` structural gate → `validate_field_wiring`, structural-first ordering).
- On-disk/alias keys correct: `from`/`to` (Edge, `serialize_by_alias`), `config`/`params`
  (`AliasChoices`, load-only), `source`/`target` (FieldMapping), `left`/`right` (JoinKeyPair),
  and `join` omitted (not `null`) when absent — matches `_dump_graph_payload`.
- Left/right ↔ from/to join orientation matches `JoinSpec`/`_check_join_fields`.

**Mechanical verification (re-ran, not taken on trust):** wrote the README's YAML example to a
scratch file, loaded it via `load_graph_from_yaml`, and ran both `validate` and
`validate_field_wiring` — validates clean. Dumped via `dump_graph_to_json`; output matches the
JSON form shown in the README (same keys, order, values, including `constant: null` preserved and
the derived `source: null` mapping).

**AC coverage:** (1) all six concepts documented with typed errors ✓; (2) annotated end-to-end
YAML example, fake names, authorable-valid ✓; (3) JSON form + alias/on-disk-key table ✓;
(4) cross-links to DANDER-2–8 + the three steering files, explicit scope boundary ✓; (5) accurate
to merged code, join product decision reflected and pointed at the Decision Log ✓.

**Security:** no credential-shaped literals in the diff (grep only hit prose security warnings);
the sole "sensitive" example value is a `sensitivity: pii` tag, i.e. a label not a value — exactly
what `steering/01-security.md` permits. No secrets/PII in any example. Docs-only: no `.py` file
modified (README is the only untracked/added file; the modified `.py` files are the merged
DANDER-4–8 model work this doc describes).

**Non-blocking observations (correctly surfaced by the docs agent, not fixed here — both are
out of scope for a docs-only ticket and were flagged rather than silently invented, per the
design):**
1. `dander.pipeline.__init__.__all__` does not re-export `NodeField`, `FieldMapping`,
   `Transformation`, `TransformationKind`, `JoinSpec`, `JoinKeyPair`, `JoinType`. The README
   documents the real submodule import paths and calls out the asymmetry. Candidate follow-up
   ticket for API-surface consistency.
2. No Decision Log entry in `steering/00-project-overview.md` yet records the join-on-graph
   product decision (DANDER-7). The README flags this honestly instead of fabricating an entry.
   Candidate follow-up ticket to append the entry.

Neither observation blocks this ticket. Status → `done`.
