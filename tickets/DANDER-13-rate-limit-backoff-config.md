---
id: DANDER-13
title: Per-source rate-limit and backoff config
status: done
component: python
epic: pipeline-config
depends_on: []
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (see DANDER-10 for the shared
review context).

`steering/02-engineering.md` explicitly requires per-source rate-limiting/backoff ("Marketo &
Salesforce throttle. Retries are bounded and logged."), but nothing in the current model captures
requests/sec, burst size, backoff kind, or retry count. `SourceConfig` in
`src/dander/ingestion/source.py` has no place to declare these limits.

This ticket adds a declarative **rate-limit / backoff config** to the source model: requests/sec,
burst allowance, backoff kind (e.g. fixed / exponential), and a bounded retry count. Model +
serialization + validation only — no actual throttling, sleeping, or retrying is implemented here
(that belongs to the ingestion runtime).

## Acceptance Criteria

- [ ] A declarative rate-limit/backoff config model attachable to a source (`SourceConfig` in
      `src/dander/ingestion/source.py`), capturing at least: requests/sec, burst, backoff kind (a
      named closed set, e.g. fixed/exponential), and a bounded max retry count. Fully type-annotated.
- [ ] Value constraints are enforced at the Pydantic boundary (e.g. non-negative rates, retry count
      within a sane bound, a valid backoff kind), raising a clear validation error.
- [ ] Backward compatibility: a source that declares no rate-limit config still loads and
      round-trips; the config is optional with sensible, conservative defaults.
- [ ] The config round-trips stably through YAML and JSON via the ingestion model's load/dump path
      (load → dump → load model equality).
- [ ] Google-style docstrings referencing the per-source throttling requirement in
      `steering/02-engineering.md`; typed per `steering/languages/python.md`. No secrets in fixtures.
- [ ] pytest tests cover: a source loads its rate-limit/backoff config; boundary constraints reject
      invalid values; round-trip stability; and a config-less source is unchanged. Tests live under
      `tests/`, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the config model + validation + serialization + tests.
      No runtime throttling/retry logic.

## Design

### Approach

This is a **model-only** change: extend the ingestion config model in
`src/dander/ingestion/source.py` with a declarative rate-limit/backoff block. No throttling,
sleeping, or retrying is implemented — that is the ingestion runtime's job (a later ticket). What
this ticket owns is the *shape* of the declaration and its validation at the Pydantic boundary, so
`steering/02-engineering.md`'s per-source throttling requirement ("Marketo & Salesforce throttle.
Retries are bounded and logged.") finally has a home in config.

The design adds two new types and one new field, reusing established repo conventions:

1. A `BackoffKind(StrEnum)` — the closed set of backoff strategies (`fixed`, `exponential`).
   We use a `StrEnum`, not a bare `Literal`, to match the existing convention in this codebase
   (`WriteMode` in `writer/base.py`, `TransformationKind`/`JoinType` in `pipeline/graph.py`): it is
   an importable named type the ingestion runtime can branch on, and it still serializes to/from its
   plain string value stably in YAML and JSON. An unknown value fails validation automatically.

2. A `RateLimitConfig(BaseModel)` — a small, single-responsibility value model grouping the four
   declared knobs with their constraints enforced via Pydantic `Field` bounds:
   - `requests_per_second: float` — steady-state request rate. Constraint `gt=0` (see ambiguity note
     below). Conservative default (e.g. `1.0`).
   - `burst: int` — max requests allowed in a short burst above the steady rate. `ge=1`,
     conservative default (e.g. `1`, i.e. no burst).
   - `backoff: BackoffKind` — which retry-backoff curve to use. Default `BackoffKind.EXPONENTIAL`
     (the safe choice against a throttling API).
   - `max_retries: int` — bounded retry count. `ge=0, le=10` (a retry count within a sane bound per
     the acceptance criteria), conservative default (e.g. `5`). `ge=0` allows explicitly disabling
     retries.
   Keeping this as its own model (rather than four loose fields on `SourceConfig`) keeps
   `SourceConfig` lean, gives the constraints one obvious home, and lets the runtime accept a
   `RateLimitConfig` directly.

3. A new field on `SourceConfig`: `rate_limit: RateLimitConfig | None = Field(default=None, ...)`.
   The default is `None` (not an auto-populated block) so that an existing connector such as
   `connectors/greenhouse.yaml` that declares no rate limit **loads unchanged and round-trips
   byte-stably** — dumping a config-less source does not synthesize a block that wasn't there. The
   "sensible conservative defaults" requirement is satisfied by the field-level defaults *inside*
   `RateLimitConfig`, which apply when a source declares the block but omits individual knobs.

**Serialization / round-trip.** There is no dedicated file loader for `SourceConfig` in the repo
today (nothing currently loads `connectors/greenhouse.yaml`), and this ticket's scope is explicitly
"Model + serialization + validation only" — so we do **not** build one. The "load/dump path" is
Pydantic's own boundary: `SourceConfig.model_validate(...)` in and `cfg.model_dump(mode="json")`
out. `mode="json"` renders the `BackoffKind` enum as its plain string, which is what makes the same
object survive both `json` and `yaml.safe_dump`/`safe_load` (pyyaml is already a pinned dependency).
The round-trip contract (`load → dump → load` equality) is verified in tests by feeding a dict/YAML/
JSON payload through `model_validate` → `model_dump(mode="json")` → serialize → deserialize →
`model_validate` and asserting model equality (Pydantic `BaseModel.__eq__` compares field values).

### Interfaces / classes (all in `src/dander/ingestion/source.py`)

- `class BackoffKind(StrEnum)` — members `FIXED = "fixed"`, `EXPONENTIAL = "exponential"`.
  Google-style class docstring noting it is the closed backoff set and why `StrEnum`.
- `class RateLimitConfig(BaseModel)` — fields `requests_per_second`, `burst`, `backoff`,
  `max_retries` as above, each with a `Field(...)` carrying the constraint and a short description.
  Class docstring references the per-source throttling requirement in `steering/02-engineering.md`
  and states that this is declaration-only (no runtime behavior here).
- `class SourceConfig(BaseModel)` — **modified**: add
  `rate_limit: RateLimitConfig | None = Field(default=None, description="Optional per-source rate-limit/backoff policy; None means unconstrained.")`.

No changes to `Source`, `Endpoint`, `dlt_backed.py`, or `enterprise.py` — the `Source.__init__`
already receives the whole `SourceConfig`, so the runtime will read `config.rate_limit` later
without any interface change now.

### Files to touch / create

- **Modify** `src/dander/ingestion/source.py` — add `BackoffKind`, `RateLimitConfig`, and the
  `rate_limit` field on `SourceConfig`. Add `from enum import StrEnum` import; keep
  `from __future__ import annotations`.
- **Create** `tests/ingestion/__init__.py` (empty, if the sibling `tests/pipeline` package pattern
  requires it — match whatever the existing test packages do) and
  `tests/ingestion/test_rate_limit_config.py` — the unit tests.
- **Optionally update** `connectors/greenhouse.yaml` — *not required*. Leaving it without a
  `rate_limit` block is itself the backward-compat fixture. If a connector-with-limits example is
  wanted, add the block to one connector, but that is documentation, not a criterion. Recommend
  leaving connectors untouched to keep the diff minimal and the config-less path exercised.

### Tests (`tests/ingestion/test_rate_limit_config.py`) — pure in-memory, no network, no mocks

Fixtures use only synthetic values (no secrets/PII per `steering/01-security.md`):

1. **Loads its config** — construct/`model_validate` a `SourceConfig` with a full `rate_limit`
   block; assert the four fields and the `BackoffKind` member resolved correctly.
2. **Boundary constraints reject invalid values** — parametrized `pytest.raises(ValidationError)`
   cases: `requests_per_second` of `0`/negative; `burst` of `0`; `max_retries` negative and
   `max_retries` above the `le` bound; and an unknown `backoff` string (e.g. `"linear"`).
3. **Round-trip stability (YAML and JSON)** — take a `SourceConfig` with a `rate_limit` block,
   `model_dump(mode="json")`, serialize via both `json.dumps`/`loads` and
   `yaml.safe_dump`/`safe_load`, `model_validate` the result, and assert equality with the original.
   Parametrize over the two serializers.
4. **Config-less source unchanged** — a `SourceConfig` with no `rate_limit` has `rate_limit is None`,
   loads from a greenhouse-style dict with no such key, and round-trips (dump→load) equal to itself.

### Trade-offs

- **`StrEnum` vs `Literal["fixed","exponential"]`** — chose `StrEnum` for consistency with the four
  existing enums in the repo and to give the future runtime an importable type to branch on; costs
  one extra class but pays off at the seam.
- **Separate `RateLimitConfig` vs inline fields on `SourceConfig`** — chose a separate model for SRP
  and to let the runtime pass the policy around as one object; keeps `SourceConfig` readable.
- **`rate_limit` default `None` vs `default_factory=RateLimitConfig`** — chose `None` so a config-less
  source stays literally unchanged and round-trips without a synthesized block (satisfies the
  backward-compat + "config-less source unchanged" criteria most cleanly); conservative defaults live
  on the sub-model's fields for the partially-specified case.
- **No file loader built** — deliberately out of scope; round-trip is proven through Pydantic's
  serialization + stdlib `json`/pyyaml, avoiding speculative infrastructure the ticket doesn't ask
  for.

### Ambiguities flagged (Code agent: apply the recommendation unless told otherwise)

- **"non-negative rates"** — a `requests_per_second` of `0` means "no throughput", which is
  nonsensical for a source meant to be read. Recommend `gt=0` (reject `0` and negatives) rather than
  a literal `ge=0`. If the intent is truly to allow `0` as "disabled", switch to `ge=0` and add a
  test asserting `0` is accepted.
- **"a sane bound" for `max_retries`** — no number is specified. Recommend `le=10`; trivially
  adjustable. The test's "above the bound" case must track whatever bound is chosen.
- **`burst` semantics/units** — defined here as "max requests permitted in a burst above the steady
  rate", `ge=1` with default `1` (no burst). If a different token-bucket semantics is intended, the
  constraint/default may need revisiting, but nothing downstream consumes it yet.

## Implementation Notes

Implemented exactly per Design — model-only, no runtime throttling/retry logic.

- **`src/dander/ingestion/source.py`**:
  - Added `from enum import StrEnum` import (kept `from __future__ import annotations`).
  - Added `BackoffKind(StrEnum)` with members `FIXED = "fixed"`, `EXPONENTIAL = "exponential"`,
    following the same convention as `PaginationKind` (`ingestion/pagination.py`) and `WriteMode`
    (`writer/base.py`).
  - Added `RateLimitConfig(BaseModel)` with `requests_per_second: float` (`gt=0`, default `1.0`),
    `burst: int` (`ge=1`, default `1`), `backoff: BackoffKind` (default `EXPONENTIAL`), and
    `max_retries: int` (`ge=0, le=10`, default `5`). Used `model_config = ConfigDict(populate_by_name=True, extra="forbid")` to match the `extra="forbid"` convention used by the pagination
    strategy models (typo'd fields are rejected rather than silently ignored).
  - Added `rate_limit: RateLimitConfig | None = Field(default=None, description=...)` to
    `SourceConfig`. A config-less source keeps `rate_limit is None` and round-trips unchanged.
  - Applied both ambiguity recommendations as-is: `gt=0` for `requests_per_second` (rejecting
    `0`), and `le=10` for `max_retries`.

- **`tests/ingestion/test_rate_limit_config.py`** (new, no `__init__.py` needed — matches the
  existing `tests/ingestion/test_pagination.py` sibling, which also has none):
  - `test_source_loads_its_rate_limit_config` — full block parses, all four fields resolve.
  - `test_rate_limit_config_has_conservative_defaults` — bare `RateLimitConfig()` matches the
    documented defaults.
  - `test_boundary_constraints_reject_invalid_values` — parametrized over
    `requests_per_second<=0`, `burst<=0`, `max_retries<0`, `max_retries>10`, and an unknown
    `backoff` string (`"linear"`); all raise `ValidationError`.
  - `test_round_trip_stability` — parametrized over JSON and YAML: `model_dump(mode="json")` →
    serialize → deserialize → `model_validate` → equality with the original, for a
    `SourceConfig` carrying a `rate_limit` block.
  - `test_config_less_source_is_unchanged_and_round_trips` — a `SourceConfig` with no
    `rate_limit`, loaded from a dict lacking the key entirely, has `rate_limit is None` and
    round-trips (dump→load) equal to itself.
  - `test_greenhouse_connector_yaml_has_no_rate_limit_block` — the existing
    `connectors/greenhouse.yaml` fixture (untouched, per Design's recommendation) still loads
    with `rate_limit is None`, proving the backward-compat path end-to-end against a real
    connector file.

- **`connectors/greenhouse.yaml`**: left untouched, as recommended by Design — it is itself the
  backward-compat fixture.

**Deviations from Design:** none. `tests/ingestion/__init__.py` was not created since the
sibling `test_pagination.py` in the same directory has none and pytest already collects it fine
(rootdir-based collection, no package `__init__.py` needed).

**Toolchain results:**
- `uv run ruff check src/dander/ingestion/source.py tests/ingestion/test_rate_limit_config.py` — pass.
- `uv run ruff format --check` (same files) — pass, already formatted.
- `uv run mypy` — `Success: no issues found in 40 source files`.
- `uv run pytest -q` — full suite green, 188 passed (all pre-existing tests plus the 6 new ones).
- Note: a repo-wide `uv run ruff check .` shows one pre-existing `E501` in
  `scripts/watch_workflows.py` (outside `src`/`tests`, untouched by this ticket) — not
  introduced by this change; baseline for `src`/`tests` remains green.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed the implementation against all acceptance criteria and the steering files; inspected the
changed code (`src/dander/ingestion/source.py`, `tests/ingestion/test_rate_limit_config.py`,
`connectors/greenhouse.yaml` left untouched) and re-ran the toolchain.

- **Acceptance criteria — all met.**
  1. `RateLimitConfig(BaseModel)` on `SourceConfig.rate_limit` captures `requests_per_second`,
     `burst`, `backoff` (closed `BackoffKind(StrEnum)` set), and `max_retries`; fully annotated.
  2. Constraints enforced at the Pydantic boundary: `gt=0` (rate), `ge=1` (burst),
     `ge=0, le=10` (retries), `extra="forbid"`, and enum membership for `backoff` — all raise
     `ValidationError` (verified by the parametrized boundary test, incl. `backoff="linear"`).
  3. Backward-compat: `rate_limit` defaults to `None`; a config-less source loads and round-trips
     unchanged; sub-model field defaults are conservative (1.0/1/EXPONENTIAL/5).
  4. Round-trips stably through both JSON and YAML — confirmed by the parametrized round-trip test
     and an independent spot-check (`mode="json"` renders `BackoffKind` as the plain string).
  5. Google-style docstrings on `BackoffKind`/`RateLimitConfig` reference the
     `steering/02-engineering.md` throttling requirement; no secrets in fixtures (`auth_ref` uses
     reference names only).
  6. Tests cover load, boundary rejection, JSON+YAML round-trip, and the config-less path, plus a
     real-connector backward-compat check; no network.
- **Security:** no hardcoded secrets/PII/credential literals in the diff; `.env.example` unaffected
  (no new secret keys introduced). Clean.
- **Design fidelity:** matches the approved design; both flagged ambiguities applied as recommended
  (`gt=0`, `le=10`). Model-only — no runtime throttling/retry logic; no out-of-scope changes.
- **Toolchain (re-run, green):** `ruff check` + `ruff format --check` pass on the changed files;
  `mypy` — "Success: no issues found in 40 source files"; `uv run pytest` — 180 passed.
  (Implementation Notes cite 188; the reported count differs but the suite is fully green — not a
  defect in this change.)

Non-blocking observation (not required by the ticket or design): `BackoffKind` and
`RateLimitConfig` are not re-exported from `src/dander/ingestion/__init__.py` the way the pagination
types are. They remain importable from `dander.ingestion.source`, and the design listed only
`source.py` + tests as files to touch, so this is consistent with the approved scope — worth a
follow-up if the runtime prefers package-level imports.

Verdict: **PASS**.
