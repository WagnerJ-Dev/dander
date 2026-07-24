---
id: DANDER-12
title: Model pagination as a strategy, not a free string
status: done
component: python
epic: pipeline-config
depends_on: []
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (see DANDER-10 for the shared
review context).

`Endpoint.pagination` in `src/dander/ingestion/source.py` is today a bare `str = "none"`. It cannot
express the parameters each real pagination style needs, and it invites typo'd, unvalidated values.
`steering/02-engineering.md` mandates provider-abstracted **strategies** behind one interface — the
codebase already does this for auth (`AuthStrategy`, per `steering/01-security.md`).

This ticket models pagination as a **strategy** mirroring the `AuthStrategy` pattern: a closed set of
kinds — offset, cursor, page-number, link-header — each carrying its own parameters (e.g. page-size /
limit param names, cursor field, next-link header name). It replaces the free string on `Endpoint`
with a typed, validated strategy shape. This ticket modifies the existing `Endpoint` model directly;
it does not depend on DANDER-10 (that ticket is about node-level config, this is the ingestion
endpoint model). Model + serialization + validation only; no pagination is actually performed here.

## Acceptance Criteria

- [ ] A pagination-strategy representation with a closed, named kind set covering at least: offset,
      cursor, page-number, and link-header — each with the parameters that style requires (typed, not
      a free dict where a real field is known). A "none"/no-pagination case remains expressible.
- [ ] `Endpoint.pagination` uses this typed strategy instead of a bare string; an out-of-set kind or
      a strategy missing its required params is rejected at the Pydantic boundary with a clear error.
- [ ] Backward compatibility / migration: existing connector YAML using `pagination: none` (or the
      current default) still loads, or a documented equivalent is provided; the default remains
      no-pagination.
- [ ] The pagination strategy round-trips stably through YAML and JSON for `SourceConfig`/`Endpoint`
      (load → dump → load model equality), using whatever load/dump path the ingestion model uses.
- [ ] Google-style docstrings referencing the strategy pattern (`steering/02-engineering.md`); typed
      per `steering/languages/python.md`. No secrets in params, defaults, or fixtures.
- [ ] pytest tests cover: each pagination kind parses with its params; an invalid kind and a
      missing-required-param case are rejected; round-trip stability; and the no-pagination default.
      Tests live under `tests/`, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the pagination-strategy model + its validation +
      serialization + tests. No actual paging/HTTP logic.

## Design

### Approach

Model pagination as a **typed, discriminated strategy** — one config model per pagination style,
each carrying exactly the parameters that style needs — mirroring the strategy pattern the codebase
already uses for auth (`AuthStrategy`, `steering/01-security.md`) and for the closed kind sets in
`pipeline/graph.py` (`TransformationKind`, `JoinType`) and `writer/base.py` (`WriteMode`). The
closed kind set is a `StrEnum` (`PaginationKind`), matching the house convention of named,
importable enums that still serialize to/from plain strings stably in YAML and JSON.

The five kinds are expressed as a **Pydantic v2 discriminated union** on the `kind` field, not a
single model with a big optional-field grab-bag. This is the key design choice: a discriminated
union gives each style its own model with its own **required, typed** parameters (satisfying "typed,
not a free dict where a real field is known"), and Pydantic rejects an out-of-set `kind` and a
missing required param at the parse boundary with a clear error — no hand-rolled `model_validator`
cross-field logic needed. (Contrast `Transformation` in `graph.py`, which is a single model with a
`model_validator` precisely because its kinds share/overlap an optional payload; pagination kinds
have genuinely disjoint params, so the union is the cleaner fit.)

Because each style is inert config (no HTTP/paging happens here — that's explicitly out of scope),
these are plain `BaseModel`s, not behavioral ABCs. The behavioral seam (a future
`build_next_request` / `extract_next_cursor`) is deliberately **not** built — no ticket asks for it
and it would be speculative. The docstrings name the strategy pattern and point at that future seam.

**Backward compatibility** is handled with a `field_validator(mode="before")` on
`Endpoint.pagination` that coerces a bare string `s` into `{"kind": s}`. This keeps the existing
`connectors/greenhouse.yaml` (which uses `pagination: link_header` and relies on the `none` default)
loading unchanged, and keeps `pagination: none` valid. Any kind whose parameters are all defaulted
(`none`, `offset`, `page_number`, `link_header`) therefore also accepts the bare-string shorthand;
`cursor` has one genuinely required, no-sensible-default param (`next_cursor_path`) and so must be
written in object form — which conveniently gives the AC's "missing required param is rejected" case
a natural home. The new `Endpoint.pagination` default is `NoPagination()` via `default_factory`, so
the default stays no-pagination.

**Round-trip** uses Pydantic's built-in path plus `yaml`, exactly like `pipeline/graph.py`:
`SourceConfig.model_validate(yaml.safe_load(text))` to load and
`yaml.safe_dump(cfg.model_dump(by_alias=True, mode="json"))` to dump. `mode="json"` renders the
`StrEnum` discriminator as its plain string value; reloading re-selects the correct union member via
the discriminator, so `load → dump → load` is model-equal. Note: a dumped strategy always comes back
in **object** form (`{kind: link_header, header_name: Link, rel: next}`), never the bare-string
shorthand — round-trip equality still holds because the reloaded model is identical; the bare string
is an input convenience only. The ingestion module has **no dedicated SourceConfig YAML loader**
today (unlike the graph module's `load_graph_from_yaml`); adding one is out of scope, so tests drive
the round-trip through `model_validate`/`model_dump` + `yaml` directly.

### Interfaces / classes

New module `src/dander/ingestion/pagination.py`:

- `PaginationKind(StrEnum)` — closed set: `NONE="none"`, `OFFSET="offset"`, `CURSOR="cursor"`,
  `PAGE_NUMBER="page_number"`, `LINK_HEADER="link_header"`.
- `NoPagination(BaseModel)` — `kind: Literal[PaginationKind.NONE] = PaginationKind.NONE`. No params;
  the explicit "single request, no paging" case.
- `OffsetPagination(BaseModel)` — `kind: Literal[PaginationKind.OFFSET]`; params (all defaulted):
  `limit_param: str = "limit"`, `offset_param: str = "offset"`, `page_size: int = 100`.
- `PageNumberPagination(BaseModel)` — `kind: Literal[PaginationKind.PAGE_NUMBER]`; params (all
  defaulted): `page_param: str = "page"`, `size_param: str = "per_page"`, `page_size: int = 100`,
  `start_page: int = 1`.
- `CursorPagination(BaseModel)` — `kind: Literal[PaginationKind.CURSOR]`; params:
  `next_cursor_path: str` (**required, no default** — response location of the next cursor, e.g.
  `"meta.next_cursor"`; genuinely source-specific), plus defaulted `cursor_param: str = "cursor"`,
  `size_param: str | None = None`, `page_size: int | None = None`.
- `LinkHeaderPagination(BaseModel)` — `kind: Literal[PaginationKind.LINK_HEADER]`; params (all
  defaulted): `header_name: str = "Link"`, `rel: str = "next"`. (This is what Greenhouse Harvest
  uses — RFC 5988 `Link` header, `rel="next"`.)
- `PaginationStrategy` — module-level type alias:
  `Annotated[NoPagination | OffsetPagination | CursorPagination | PageNumberPagination | LinkHeaderPagination, Field(discriminator="kind")]`.
  All application code (and `Endpoint`) depends on this alias, never a concrete kind.

Each kind model sets `model_config = ConfigDict(populate_by_name=True, extra="forbid")` — `extra="forbid"`
so a typo'd/unknown param (e.g. `page_sixe`) is rejected rather than silently dropped, reinforcing the
"no free string / no unvalidated values" intent of the ticket. `page_size`/`start_page` use
`Field(gt=0)` / `Field(ge=…)` so nonsensical values are rejected too.

Modified `src/dander/ingestion/source.py`:

- `Endpoint.pagination: PaginationStrategy = Field(default_factory=NoPagination)` replaces
  `pagination: str = "none"`.
- New `@field_validator("pagination", mode="before")` `_coerce_bare_pagination_kind` — wraps a bare
  `str` into `{"kind": <str>}`; passes dicts and model instances through untouched.
- Add `model_config = ConfigDict(populate_by_name=True)` to `Endpoint` if needed for the validator
  ergonomics (only if required).

Modified `src/dander/ingestion/__init__.py`:

- Export the public surface: `PaginationKind`, `PaginationStrategy`, `NoPagination`,
  `OffsetPagination`, `CursorPagination`, `PageNumberPagination`, `LinkHeaderPagination`, plus
  re-export `Endpoint`, `SourceConfig` (currently the file is a bare docstring with no `__all__`).

### Files to touch / create

- **create** `src/dander/ingestion/pagination.py` — the enum, the five kind models, the union alias;
  Google-style docstrings referencing the strategy pattern and `steering/02-engineering.md`.
- **modify** `src/dander/ingestion/source.py` — retype `Endpoint.pagination`, add the before-validator,
  add imports.
- **modify** `src/dander/ingestion/__init__.py` — public exports / `__all__`.
- **create** `tests/ingestion/test_pagination.py` — the test cases below (add `tests/ingestion/` dir).
- `connectors/greenhouse.yaml` — **no change required** (it keeps loading via bare-string coercion);
  optionally add a test that loads it to prove backward-compat end-to-end.

### Trade-offs

- **Discriminated union vs. single model + `model_validator`** (the `Transformation` precedent):
  chose the union because pagination kinds have disjoint, individually-required params — the union
  makes each param's requiredness a first-class Pydantic constraint (better errors, less bespoke
  validator code). The `Transformation` single-model shape is right only when kinds share an
  optional payload; that's not the case here. Recorded so a reviewer doesn't flag the divergence.
- **Bare-string coercion vs. hard migration**: chose coercion so no committed connector YAML breaks
  and the ergonomic `pagination: none` / `pagination: link_header` shorthand survives. Cost: the
  dumped form is always the object shape, so a file authored as a bare string "expands" on the first
  dump — acceptable and documented.
- **`cursor.next_cursor_path` required**: makes `cursor` the one kind without bare-string shorthand.
  Chosen deliberately — there is no safe universal default for where a cursor lives in a response,
  and it gives the required-param-rejection AC a real, non-contrived case.
- **No behavioral ABC**: keeps scope to model+validation+serialization per the ticket; avoids
  speculative generality.

### Test seams

Pure, in-process, no network (`tests/ingestion/test_pagination.py`):

- **Each kind parses with its params** — construct/`model_validate` each of the five kinds (object
  form) and assert typed fields land, including `cursor` with `next_cursor_path`.
- **Bare-string coercion** — `Endpoint.model_validate({"name":…, "path":…, "pagination":"link_header"})`
  yields `LinkHeaderPagination`; `"none"` yields `NoPagination`; `"offset"`/`"page_number"` yield
  their defaulted models.
- **Invalid kind rejected** — `pagination: "keyset"` (bare) and `{"kind":"keyset"}` raise
  `ValidationError` with a clear discriminator message.
- **Missing required param rejected** — `{"kind":"cursor"}` (no `next_cursor_path`) raises
  `ValidationError`.
- **Unknown/typo'd param rejected** — `{"kind":"offset","page_sixe":10}` raises (via `extra="forbid"`).
- **No-pagination default** — `Endpoint(name=…, path=…)` has `pagination == NoPagination()`.
- **Round-trip stability** — build a `SourceConfig` with several endpoints across kinds; assert
  `SourceConfig.model_validate(yaml.safe_load(yaml.safe_dump(cfg.model_dump(by_alias=True, mode="json")))) == cfg`;
  and the same through JSON (`model_dump_json` / `model_validate_json`).
- Nothing is mocked (all pure model logic); no fixtures carry secrets or sample data
  (`steering/01-security.md`).

### Flagged for the Code agent

- The AC phrase "whatever load/dump path the ingestion model uses" resolves to **Pydantic's built-in
  `model_validate`/`model_dump` + `yaml`** — there is intentionally no `load_source_from_yaml` helper
  in this ticket (that would be its own scope). If a reviewer expects a helper, raise it rather than
  adding one here.
- Pick a single sensible `page_size` default (100 proposed) and note it's a starting value, not a
  tuned one — no paging is exercised here.

## Implementation Notes

Implemented exactly per the Design section — no deviations.

- **Created** `src/dander/ingestion/pagination.py`: `PaginationKind` (`StrEnum`: `none`, `offset`,
  `cursor`, `page_number`, `link_header`); five kind models (`NoPagination`, `OffsetPagination`,
  `CursorPagination`, `PageNumberPagination`, `LinkHeaderPagination`), each
  `ConfigDict(populate_by_name=True, extra="forbid")` with a `Literal[PaginationKind.X]`
  discriminator field and its own typed params (`page_size`/`start_page` use `Field(gt=0)`/
  `Field(ge=0)`); `CursorPagination.next_cursor_path` is the one required, no-default param.
  `PaginationStrategy` is the `Annotated[... , Field(discriminator="kind")]` union alias all
  application code depends on. Google-style docstrings throughout referencing the strategy
  pattern and `steering/02-engineering.md`/`01-security.md`.
- **Modified** `src/dander/ingestion/source.py`: `Endpoint.pagination` retyped from `str = "none"`
  to `PaginationStrategy = Field(default_factory=NoPagination)`; added
  `ConfigDict(populate_by_name=True)` and a `@field_validator("pagination", mode="before")`
  (`_coerce_bare_pagination_kind`) that wraps a bare `str` into `{"kind": <str>}` and passes
  dicts/typed instances through untouched. `SourceConfig` and `Source` untouched.
- **Modified** `src/dander/ingestion/__init__.py`: was a bare module docstring; now re-exports
  `PaginationKind`, `PaginationStrategy`, the five kind models, plus `Endpoint`, `Source`,
  `SourceConfig` via `__all__`.
- **Created** `tests/ingestion/test_pagination.py` (13 tests, no network, no sensitive fixtures):
  each kind parsing with its params; bare-string coercion for `none`/`offset`/`page_number`/
  `link_header` (parametrized); invalid kind rejected in both bare and object form; missing
  required param (`cursor` without `next_cursor_path`) rejected; unknown/typo'd param
  (`page_sixe`) rejected via `extra="forbid"`; no-pagination default; round-trip stability
  through YAML and JSON for a multi-kind `SourceConfig`
  (`model_validate(yaml.safe_load(yaml.safe_dump(model_dump(by_alias=True, mode="json")))) ==
  cfg`, and the `model_dump_json`/`model_validate_json` equivalent); a check that dumped
  pagination always renders in object form; and a backward-compat test that loads
  `connectors/greenhouse.yaml` unchanged and confirms both endpoints resolve to
  `LinkHeaderPagination()`.
- `connectors/greenhouse.yaml` — not modified, per the design; proven still-loading by the new
  backward-compat test.
- No behavioral pagination/HTTP logic added, per scope — models, validation, and serialization
  only.

**Toolchain** (repo baseline, not just touched files): `uv run ruff check .`, `uv run ruff format
--check .` (pre-existing, unrelated `scripts/watch_workflows.py` E501 predates this ticket —
confirmed via `git log`, left untouched as out of scope), `uv run mypy` (39 source files, clean),
`uv run pytest` (167 passed, including the 13 new tests) — all green.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed the implementation against all eight acceptance criteria, the steering files
(`01-security.md`, `02-engineering.md`, `languages/python.md`), and the approved Design. Inspected
`src/dander/ingestion/pagination.py`, `src/dander/ingestion/source.py`,
`src/dander/ingestion/__init__.py`, `tests/ingestion/test_pagination.py`, and
`connectors/greenhouse.yaml`.

- **AC1 (closed typed kind set):** met. `PaginationKind` StrEnum covers `none`/`offset`/`cursor`/
  `page_number`/`link_header`; five per-kind `BaseModel`s each carry their own typed params;
  `CursorPagination.next_cursor_path` is a genuinely-required typed field (not a free dict).
- **AC2 (Endpoint uses typed strategy; boundary rejection):** met. `Endpoint.pagination:
  PaginationStrategy` is a discriminated union on `kind`; out-of-set kind and missing-required-param
  both raise `ValidationError` at parse (verified by tests).
- **AC3 (backward compat / default):** met. `_coerce_bare_pagination_kind` (before-validator) keeps
  `pagination: none` / `link_header` shorthand loading; default is `NoPagination` via
  `default_factory`; `connectors/greenhouse.yaml` unchanged and proven still-loading.
- **AC4 (round-trip YAML + JSON):** met. `model_dump(by_alias=True, mode="json")` ↔
  `model_validate` and `model_dump_json` ↔ `model_validate_json` are model-equal (tests pass).
- **AC5 (docstrings/typing/no secrets):** met. Google-style docstrings on module/classes name the
  strategy pattern; fully typed; `extra="forbid"` and `Field(gt=0/ge=0)` guard params; no secret
  values (test `auth_ref` and connector use reference NAMES only).
- **AC6 (tests):** met. 13 pure, no-network tests cover each kind, coercion, invalid kind, missing
  param, unknown param, default, and round-trip; live under `tests/ingestion/`.
- **AC7 (toolchain green):** met for this ticket. `uv run mypy` clean (39 files); `uv run pytest`
  167 passed; ingestion files pass `ruff check`/`ruff format`. The one `ruff check` error
  (`scripts/watch_workflows.py:37` E501) is pre-existing (commit 7a75efa), untouched by this ticket
  (`git diff` empty for that file), and out of scope — not a regression.
- **AC8 (no scope creep / no HTTP logic):** met. Model + validation + serialization only; no
  behavioral paging seam built.

Security: clean — no hardcoded secrets, no PII in fixtures/logs, references-by-name only.

Non-blocking note (no action required): the module/class docstrings cite `steering/01-security.md`
for the strategy-pattern precedent; the AC parenthetically points at `steering/02-engineering.md`
(where the pattern is mandated). The strategy pattern is explicitly and correctly referenced, so
this is a cosmetic citation nit, not a defect.
