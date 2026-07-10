---
id: DANDER-1
title: Implement parse_refs to extract ref() dependencies from model SQL
status: done
component: python
epic: transform
depends_on: []
created: 2026-07-09
---

## Context

The Transform module (see `steering/00-project-overview.md`, Transform row and the 2026-07-09
"Transform = own engine" decision) builds a dependency DAG from Jinja-style `ref()` calls in a
model's SQL, then topologically executes models. `parse_refs(sql: str) -> list[str]` in
`src/dander/transform/model.py` is the seam that feeds that DAG: it turns raw model SQL into the
ordered list of upstream model names. It currently raises `NotImplementedError`.

Our models use exactly the `{{ ref('name') }}` form — see
`models/staging/stg_greenhouse__candidates.sql`, which references `{{ ref('raw_greenhouse_candidates') }}`.
Because the DAG's correctness depends entirely on this parse, the extraction must be precise: no
missed refs, no phantom refs, and stable ordering.

## Acceptance Criteria

- [ ] `parse_refs(sql: str) -> list[str]` is implemented (no `NotImplementedError`) and returns the
      referenced model names in order of first appearance, de-duplicated (first occurrence wins).
- [ ] Parses the `{{ ref('name') }}` form; the quoted name may use single OR double quotes.
- [ ] Tolerates arbitrary whitespace (including none) inside the `{{ }}` braces and around the
      parentheses and quotes, e.g. `{{ref("x")}}` and `{{  ref (  'x'  )  }}` both yield `["x"]`.
- [ ] Anything that is not a `ref()` call is ignored (e.g. other Jinja expressions, SQL comments
      mentioning "ref", function-like text such as `pref('x')` must not match).
- [ ] Returns an empty list when the SQL contains no refs, and for empty-string input.
- [ ] Public function has a Google-style docstring with `Args`/`Returns` and a precise return
      contract, and is fully type-annotated (per `languages/python.md`).
- [ ] pytest unit tests cover: multiple distinct refs (order preserved), duplicate refs
      (de-duplicated, order preserved), no refs, empty string, single-quote and double-quote names,
      and whitespace variations (tight and loose). Tests live under `tests/` and require no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations (secrets, style, docs); no scope beyond `parse_refs` and its tests.

## Design

### Approach

`parse_refs` is the pure extraction seam that feeds the transform DAG. Every acceptance
criterion describes exactly one supported surface form — `{{ ref('name') }}` — with quote
and whitespace tolerance and precise non-matching (no `pref('x')`, no bare comment text).
This is a bounded, well-specified string-extraction problem, so the implementation is a
single **compiled, anchored regex** applied with `re.finditer`, followed by an
order-preserving de-duplication. No rendering, no external state, no I/O — the function
stays a small pure function (per `languages/python.md`: "push side effects to the edges";
`02-engineering.md`: DAG resolution is unit-tested business logic).

**Why regex over the alternatives (deliberate, not default):**
- **Jinja2 full render** would require a populated environment with a recording `ref`
  callable *and* lenient handling of every other undefined template construct in real model
  SQL; undefined macros/vars raise at render time, adding failure surface for a task that
  only needs to read one call form. Rejected as heavier and more fragile than the ticket asks.
- **sqlglot** parses SQL, not Jinja `{{ }}` delimiters, so it cannot see refs pre-render. It
  is the right tool for the *downstream* DAG/column analysis (per the Decision Log), not for
  this lexical extraction.
- **Regex** matches precisely the one documented form, adds no dependency, is pure, fast, and
  trivially parametrizable in tests. It fully satisfies every acceptance criterion.

`parse_refs` remains the stable seam: if the template surface later grows (macros, a
two-arg `ref('pkg', 'name')`, other tags), the sanctioned upgrade is a Jinja2 **AST visitor**
(`Environment().parse(sql)` walking `nodes.Call` where the callee is `ref`), which reuses the
already-pinned `jinja2` dependency and honors the "Jinja2 ref()" Decision Log entry — without
over-building now (steering: no speculative generality). This is noted in-code as the evolution
path; it is out of scope for this ticket.

### Interface / structure

No new classes or abstractions — this is a leaf function on an existing module, and inventing
an interface here would be speculative generality. Two elements in `src/dander/transform/model.py`:

- **`_REF_PATTERN: re.Pattern[str]`** — module-level compiled constant (UPPER via leading
  underscore for private module state; compiled once, no per-call cost, no import-time side
  effects beyond a `re.compile`). Pattern shape:

  ```
  \{\{\s*ref\s*\(\s*(['"])(.*?)\1\s*\)\s*\}\}
  ```

  - Anchored on `\{\{\s*ref` so only whitespace may sit between `{{` and `ref` — this is what
    rejects `pref('x')` and `{{ myref('x') }}` (a non-space char precedes `ref`), and rejects
    bare comment text like `-- references ref('x')` (no `{{`).
  - `\s*` at every documented flex point (inside braces, around parens, around quotes) covers
    both tight `{{ref("x")}}` and loose `{{  ref (  'x'  )  }}`.
  - `(['"]) … \1` is a **backreference**: the closing quote must match the opening one, so
    `'name'` and `"name"` both match while a mismatched `'x"` does not. Group 2 (`.*?`,
    non-greedy) is the captured model name.

- **`parse_refs(sql: str) -> list[str]`** — iterate `_REF_PATTERN.finditer(sql)`, collect
  `match.group(2)` in encounter order, then return `list(dict.fromkeys(names))`.
  `dict.fromkeys` gives first-appearance order with de-duplication (first occurrence wins) in
  one idiomatic expression. Empty/no-ref input naturally yields `[]` (no matches → empty dict).
  Full Google-style docstring with `Args`/`Returns` and the precise return contract; fully
  type-annotated (signature already correct — remove the `NotImplementedError`).

### Files to touch

- **`src/dander/transform/model.py`** (edit) — add `import re`; add the `_REF_PATTERN` constant;
  implement `parse_refs` body; expand its docstring; add a one-line comment pointing at the
  Jinja2-AST evolution path. No change to `Model`, `Materialization`, or the function signature.
- **`tests/transform/test_model.py`** (new) — pytest unit tests for `parse_refs`. Mirror the
  source domain grouping (`transform/`) rather than the current flat `tests/` layout, per the
  "group by domain" rule in `languages/python.md`. No `__init__.py` needed (pytest rootdir
  import). Pure function → **no mocks, no network, no fixtures with data**.

### Test seams

`parse_refs` is pure, so the test is direct input→output assertion, best expressed with
`@pytest.mark.parametrize`. Cases (one per acceptance bullet):
- multiple distinct refs → order of first appearance preserved;
- duplicate refs → de-duplicated, first-occurrence order preserved;
- no refs → `[]`; empty string → `[]`;
- single-quote and double-quote names each parse;
- whitespace variants: tight `{{ref("x")}}` and loose `{{  ref (  'x'  )  }}` → `["x"]`;
- negative cases ignored: `pref('x')`, `{{ myref('x') }}`, a SQL comment mentioning `ref`
  without braces, and an unrelated Jinja expression → no phantom matches;
- (recommended) the real `stg_greenhouse__candidates.sql` body → `["raw_greenhouse_candidates"]`
  as an integration-style sanity check.

### Trade-offs / notes

- **Regex vs. parser** resolved above — regex is the right altitude for this ticket's exact
  scope; the Jinja2-AST path is documented for when scope grows.
- **Name validation is intentionally out of scope.** `parse_refs` returns names verbatim as
  written between the quotes; rejecting invalid identifiers or resolving packages belongs to the
  downstream DAG builder, not this lexical seam (single responsibility).
- **No ambiguous acceptance criteria.** One edge the ticket doesn't pin down — an empty name
  `ref('')` — is left to match as `""` (the regex `.*?` allows it); this is harmless and not
  worth special-casing, but flagged here for the Code agent's awareness.
- **Security:** nothing touches secrets, credentials, or ingested data; test fixtures are
  synthetic model SQL only. No `01-security.md` surface.

## Implementation Notes

Implemented exactly per Design, no deviations.

- `src/dander/transform/model.py`: added `import re` and the module-level compiled constant
  `_REF_PATTERN` (`\{\{\s*ref\s*\(\s*(['"])(.*?)\1\s*\)\s*\}\}`) with a comment explaining the
  anchoring (rejects `pref('x')`, `{{ myref('x') }}`, and bare comment text) and the quote
  backreference. `parse_refs` now iterates `_REF_PATTERN.finditer(sql)`, collects
  `match.group(2)` in encounter order, and returns `list(dict.fromkeys(names))` for
  order-preserving de-duplication. Docstring expanded to Google-style with `Args`/`Returns` and
  the precise contract (verbatim names, first-occurrence order, `[]` for no-refs/empty string).
  A one-line comment documents the Jinja2 AST-visitor evolution path (out of scope here) per the
  Decision Log. No changes to `Model`, `Materialization`, or the function signature.
- `tests/transform/test_model.py` (new): parametrized pytest cases covering every acceptance
  bullet — multiple distinct refs (order preserved), duplicate refs (de-duplicated, order
  preserved), no refs, empty string, single- and double-quote names, tight and loose whitespace,
  and the negative cases (`pref('x')`, `{{ myref('x') }}`, a comment mentioning "ref", an
  unrelated Jinja expression). Also added the recommended integration-style test reading the real
  `models/staging/stg_greenhouse__candidates.sql` and asserting
  `["raw_greenhouse_candidates"]`. Pure function, no mocks/network/fixtures with data.
- Tests live under `tests/transform/` (new subdir, mirrors `src/dander/transform/`), no
  `__init__.py`, per the "group by domain" rule and pytest rootdir import.
- Toolchain: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, and
  `uv run pytest` all pass (16 tests passed, 0 failures; no pre-existing issues introduced).
- No steering violations: no secrets, no I/O/network, no scope beyond `parse_refs` and its tests.
- Per Design's noted ambiguity, `ref('')` matches and yields `""` (unspecial-cased, as documented
  — not worth guarding against; left to the downstream DAG builder if it ever matters).

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-09 — PR-Review: PASS

Reviewed `src/dander/transform/model.py` and `tests/transform/test_model.py` against all
acceptance criteria, the Design, and steering (`01-security.md`, `02-engineering.md`,
`languages/python.md`).

- **Acceptance criteria — all met.** `parse_refs` is implemented (no `NotImplementedError`),
  returns first-appearance order with de-dup via `list(dict.fromkeys(...))` (first occurrence
  wins). Handles `{{ ref('name') }}` with single/double quotes and arbitrary whitespace at every
  flex point (`{{ref("x")}}` and `{{  ref (  'x'  )  }}` both verified). Non-ref text is rejected:
  confirmed `pref('x')`, braced `{{ pref('x') }}`, `{{ myref('x') }}`, comment text `-- ... ref('x')`,
  unrelated `{{ some_var }}`, and mismatched quotes `{{ ref('x") }}` all yield `[]`. Empty and
  no-ref input yield `[]`. Google-style docstring with `Args`/`Returns` and a precise contract;
  fully type-annotated.
- **Tests.** Parametrized cases cover every acceptance bullet plus an integration-style check
  against the real `models/staging/stg_greenhouse__candidates.sql` → `["raw_greenhouse_candidates"]`.
  Pure, no network/mocks/fixtures. Located under `tests/transform/` per the group-by-domain rule.
- **Toolchain green.** `uv run ruff check` (all passed), `uv run ruff format --check` (clean),
  `uv run mypy` (no issues, 23 files), `uv run pytest` (16 passed).
- **Security.** No secrets/credentials/PII anywhere in the diff; synthetic SQL only. No `.env`
  surface. No `01-security.md` violations.
- **Design fidelity & scope.** Implemented exactly per the approved regex Design; `_REF_PATTERN`
  compiled once at module level with the documented backreference and anchoring; Jinja2-AST
  evolution path noted in-code. No changes to `Model`/`Materialization`/signature; no scope beyond
  `parse_refs` and its tests. Documented `ref('')` → `['']` edge is acceptable and out of scope.

Verdict: **PASS**. Status set to `done`.
