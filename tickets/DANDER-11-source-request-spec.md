---
id: DANDER-11
title: Request/payload spec for source nodes
status: done
component: python
epic: pipeline-config
depends_on: [DANDER-10]
created: 2026-07-22
---

## Context

Originated from the pipeline-graph/ingestion-model gap analysis (see DANDER-10 for the shared
review context).

No model exists today for **how a source node calls its API**: the HTTP method (GET/POST/PUT/…),
request headers, query parameters, and a request body template are all unrepresented. A source that
must POST a query body, send custom headers, or pass query params cannot be described declaratively.

This ticket adds a declarative **request/payload spec** to the typed `source`-node config introduced
in DANDER-10. Per `steering/01-security.md`, header and body **values** must be **secret references
or field references only** — never literal secret values; secrets live in Secret Manager / env and
are referenced indirectly. This is model + serialization + validation only; nothing here performs an
HTTP request.

## Acceptance Criteria

- [ ] A declarative request-spec model attachable to a `source`-node config (DANDER-10): HTTP method
      (constrained to a known set, e.g. GET/POST/PUT/PATCH/DELETE), headers, query params, and a
      request body template. Fully type-annotated.
- [ ] Header and body/param values are constrained/documented to be **secret references or field
      references only** — never inline secret literals (`steering/01-security.md`). A literal that is
      shaped like a raw credential is rejected or explicitly disallowed by the model contract.
- [ ] Backward compatibility: a source node that declares no request spec (e.g. a simple GET
      endpoint) still loads and round-trips; the spec is optional with a sensible default method.
- [ ] The request spec round-trips stably through **both** YAML and JSON via the existing load/dump
      functions: load → dump → load yields an equivalent graph (model equality).
- [ ] Google-style docstrings state that values are secret/field references only and are never
      resolved or sent here. Typed per `steering/languages/python.md`.
- [ ] pytest tests cover: a source node loads a request spec (method + headers + params + body) from
      YAML and JSON; round-trip stability in both formats; the secret-reference constraint (a
      reference is accepted, an inline secret literal is rejected); and a spec-less source node is
      unchanged. Tests live under `tests/`, use only synthetic reference tokens, no network.
- [ ] `uv run ruff check`, `uv run mypy`, and `uv run pytest` all remain green (baseline is green).
- [ ] No steering violations; no scope beyond the request-spec model + serialization + validation +
      tests. No HTTP execution, no secret resolution.

## Design

### Approach

Add a declarative, inert **request/payload spec** that a `source`-node config can carry: an HTTP
method, headers, query params, and a request-body template. Nothing here performs a request,
resolves a secret, or renders a template — it is model + serialization + validation only, matching
the "records intent" posture of the rest of `dander.pipeline`.

This ticket depends on DANDER-10, which introduces the typed, per-`Node.type` config models
(`SourceNodeConfig` / `TransformNodeConfig` / `TargetNodeConfig`). DANDER-11 adds the request spec in
its **own module** and extends DANDER-10's `SourceNodeConfig` with one optional field
(`request: RequestSpec | None = None`). In the `feature` workflow DANDER-10 builds before DANDER-11
(serial `depends_on`), so the source config model exists by the time this is coded; the code agent
must fit whatever attribute/module name DANDER-10 actually lands (see Notes). Everything else reuses
the existing `graph.py` load/dump functions unchanged — `RequestSpec` is a plain Pydantic v2 model,
so it round-trips natively through `model_validate` / `model_dump`.

The security-sensitive core is AC #2: header/param/body **values** must be **secret references or
field references only**, never inline secret literals. Rather than force *every* value to be a
reference (which would break benign static headers like `Content-Type: application/json`), the model
recognizes a small, documented **reference grammar** and applies two complementary, documented rules
in a single `model_validator`:

- **Rule A — sensitive positions (deterministic).** A header or query param whose *name* is in a
  documented sensitive set (`authorization`, `proxy-authorization`, `x-api-key`, `api-key`,
  `x-auth-token`, `cookie`, `set-cookie`; case-insensitive) MUST be a recognized reference. A
  non-reference literal in one of those positions raises `ValueError`. This is the airtight guarantee
  for the positions that actually carry credentials, and it catches even short/opaque secrets that a
  shape heuristic would miss.
- **Rule B — credential-shaped literals anywhere (defense in depth).** Any value in any position
  that is *not* a recognized reference and matches a raw-credential shape is rejected: a
  `Bearer `/`Basic `/`Token ` auth prefix followed by an inline token, a PEM block (`-----BEGIN`),
  known key prefixes (e.g. `sk_`/`sk-`/`AKIA`/`ghp_`/`xox`-style), or a long high-entropy
  base64/hex run with no whitespace. Benign literals (`application/json`, an `Accept` value, a
  pagination token name) pass. Documented as best-effort, not a proof — the guarantee comes from
  Rule A plus the documented contract.

Recognized references (always allowed, never resolved here):
- **Secret reference:** `secret:<name>`, `env:<VAR_NAME>`, or a Secret Manager resource name
  (`projects/…/secrets/…/versions/…`) — consistent with `SourceConfig.auth_ref`.
- **Field reference:** `field:<field_name>` or mustache `{{ <field_name> }}`.

Error messages name the **position** (header/param key, or `body`) and the rule violated, and
**never echo the offending value** (`steering/01-security.md`).

### Interfaces / classes (new module `src/dander/pipeline/request_spec.py`)

- **`HttpMethod(StrEnum)`** — closed method set `GET/POST/PUT/PATCH/DELETE`, following the
  `TransformationKind` / `JoinType` precedent (named, importable, serializes to/from its plain string
  value stably; an out-of-set value fails at the Pydantic boundary). `GET` is the default.
- **Reference-classification helpers (pure functions, unit-testable in isolation):**
  - `is_secret_reference(value: str) -> bool`
  - `is_field_reference(value: str) -> bool`
  - `is_reference(value: str) -> bool` (either of the above)
  - `looks_like_raw_credential(value: str) -> bool` (Rule B tripwire)
  - `SENSITIVE_HEADER_NAMES: frozenset[str]` / `SENSITIVE_PARAM_NAMES: frozenset[str]` constants.
- **`RequestSpec(BaseModel)`** — `model_config = ConfigDict(populate_by_name=True)`; fields:
  - `method: HttpMethod = HttpMethod.GET` (sensible default → AC #3 backward compat).
  - `headers: dict[str, str] = Field(default_factory=dict)`
  - `query_params: dict[str, str] = Field(default_factory=dict)` — named `query_params` (not
    `params`) to avoid colliding with the `params`→`config` alias on `Node`.
  - `body: dict[str, Any] | str | None = None` — a JSON-object body template *or* a raw string
    template (covers POST query/GraphQL bodies), mirroring the `Any`-JSON precedent
    (`Transformation.constant`, `Node.config`). Never rendered here.
  - `@model_validator(mode="after")` `_check_reference_values` — applies Rule A to `headers` and
    `query_params` by name, and Rule B to every string leaf of `headers`, `query_params`, and `body`
    (recursively walking nested dict/list leaves in an object body). Positions are validated
    deterministically; no I/O.
- **Integration:** DANDER-10's `SourceNodeConfig` gains `request: RequestSpec | None = None` with a
  Google-style docstring stating values are references only and are never resolved/sent here.

### Files to touch / create

- **Create** `src/dander/pipeline/request_spec.py` — everything above.
- **Edit** DANDER-10's source-config module (expected `src/dander/pipeline/node_config.py`; if
  DANDER-10 instead lands the typed configs inside `graph.py`, add it there) — add the optional
  `request` field + import `RequestSpec`.
- **Edit** `src/dander/pipeline/__init__.py` — re-export `HttpMethod` / `RequestSpec` alongside the
  other model classes (follow whatever export convention DANDER-10 sets for the node configs).
- **Edit** `src/dander/pipeline/graph.py` **only if needed** — if a spec-less source node dumps a
  spurious `request: null`, extend the scoped-`None`-omission pattern already used for join-less
  `join` in `_dump_graph_payload` to drop an absent `request`. Round-trip *equality* (AC #4) holds
  either way; this is for on-disk cleanliness / parity with the join precedent. Coordinate with how
  DANDER-10 serializes the nested source config.
- **Create** `tests/pipeline/test_request_spec.py` — see Test seams.
- **Edit** `src/dander/pipeline/README.md` — document the request spec and the reference contract
  (docs stay true to code).
- **No** new secret key; `.env.example` unchanged (references only, no values).

### Trade-offs

- **Plain string values + validator vs. a tagged value-union type.** A tagged union
  (`Literal | SecretRef | FieldRef` per value) would make an inline secret structurally
  impossible, but turns every header into a nested object — poor YAML ergonomics and out of step
  with the codebase's "plain value + `model_validator`" style (`Transformation`, `Node.config`).
  Chosen: plain strings + Rule A (deterministic, airtight for sensitive positions) + Rule B
  (best-effort tripwire) + documentation. Accepted residual risk: a secret hidden in a
  non-sensitive-named position that also doesn't match a known shape; mitigated by docs and the
  sensitive-name set.
- **Rule B is heuristic.** It can false-positive on a genuinely non-secret long literal; the escape
  hatch is to express it as an explicit reference. Documented as defense-in-depth, not a guarantee.
- **`body` as `dict | str | Any`.** Keeps object and string bodies both expressible without a
  second model; cost is a small recursive leaf-walk in the validator (in scope, deterministic).
- **`HttpMethod` closed to five verbs.** Matches the ticket's enumerated set; HEAD/OPTIONS omitted
  as no source needs them — extend by adding a member later without touching callers.

### Test seams (`tests/pipeline/test_request_spec.py`, synthetic tokens only, no network)

- **Pure helpers** unit-tested directly: `is_secret_reference` / `is_field_reference` /
  `is_reference` / `looks_like_raw_credential` across reference forms and benign/credential-shaped
  literals.
- **Model validation:** a `RequestSpec` with a reference `Authorization` header + reference param +
  reference-bearing body is accepted; an inline credential literal in a sensitive position (Rule A)
  and a credential-shaped literal in a plain position (Rule B) each raise `ValidationError`; a
  benign static header (`Content-Type: application/json`) is accepted; error message contains the
  position but not the value.
- **Method + serialization:** a `source` node loads a full request spec (method + headers + params +
  body) from **YAML and JSON** via `load_graph_from_yaml` / `load_graph_from_json`; load→dump→load is
  equal in **both** formats (AC #4).
- **Backward compat:** a spec-less `source` node (no `request`) loads, defaults `method` to `GET`,
  and round-trips equal (AC #3).
- All tokens synthetic (e.g. `secret:demo_key`, `field:candidate_id`, a fake `Bearer not-a-real-…`);
  no real/sensitive values committed.

### Notes / flagged ambiguities

- **DANDER-10 coupling.** The exact `SourceNodeConfig` module/attribute name is set by DANDER-10
  (not yet merged). The code agent must attach `request` to whatever DANDER-10 actually lands; the
  serialization-cleanliness edit in `graph.py` depends on how DANDER-10 dumps the nested source
  config.
- **Reference grammar is introduced here** — no templating syntax pre-exists in the repo. The
  chosen prefixes (`secret:` / `env:` / `field:` / `{{ … }}`) and Secret-Manager-resource-name form
  are a new, documented contract; confirm them before wider reuse (DANDER-16 target/writer config
  may want the same helpers — keep them importable).
- **AC #2 wording "rejected *or* explicitly disallowed"** is satisfied by Rule A (disallowed by
  contract for sensitive positions) + Rule B (rejected for credential-shaped literals).

## Implementation Notes

Implemented per the Design section, with three deviations forced by verified runtime behavior
(re-checked against `pydantic==2.13.4`, the pinned version in this environment):

1. **`looks_like_raw_credential` excludes recognized references internally**, rather than relying
   on every caller to check `is_reference` first. The Design describes it as a standalone shape
   check with callers combining it with `is_reference`; verified this is unsafe on its own — a
   legitimate Secret Manager resource name containing a numeric project id or version segment
   (e.g. `projects/1234567890/secrets/my-secret/versions/3`) can satisfy the "long, whitespace-free,
   digit-and-letter run" high-entropy heuristic and would be misflagged as a raw credential if the
   function were ever called without the `is_reference` guard ahead of it. Fix: `is_reference(value)`
   is checked first inside `looks_like_raw_credential` itself, so the function is safe to call
   directly (as its own pytest parametrization does) without relying on caller discipline. The
   model's `_check_value` still checks `is_reference` up front too (now redundant but harmless) —
   Rule A's sensitive-position requirement needs that check independently of Rule B.
2. **`RequestSpec.model_config` adds `hide_input_in_errors=True`.** Without it, AC #2/the
   "never echoes the offending value" requirement did not hold in practice: verified by direct
   repro that Pydantic's default `ValidationError` rendering appends a `repr()` of the entire
   rejected input (`input_value={'headers': {'Authorization': 'Bearer <the literal>'}, ...}`)
   after the raised `ValueError` text, leaking the literal even though the message itself only
   names the position. This mirrors the exact fix DANDER-10 made on `Node` for the same reason.
   Tests assert the offending literal is absent from the exception string, not just that the
   position name is present.
3. **`dander.pipeline.node_config`'s import of `RequestSpec` is a real (non-`TYPE_CHECKING`)
   import**, with a `# noqa: TC001` overriding ruff's suggestion to defer it. Verified with a
   minimal repro that — despite `from __future__ import annotations` making
   `SourceNodeConfig.request`'s annotation a lazy string — Pydantic still resolves that string
   against the module's globals when building `SourceNodeConfig`'s schema at class-definition
   time; deferring the import to `TYPE_CHECKING` raises `PydanticUserError: 'SourceNodeConfig' is
   not fully defined` on import. The `noqa` is commented with this rationale in place.

Also, beyond the Design's explicit interfaces:

- **On-disk cleanliness for a spec-less source node.** `graph.py`'s `_dump_graph_payload` now
  also drops a `source` node's `config.request` key when `SourceNodeConfig.request is None`
  (mirroring the pre-existing join-less-`join` omission), so a spec-less source node round-trips
  byte-identical to a pre-DANDER-11 graph rather than gaining a spurious `request: null`. Round-trip
  *equality* (AC #4) would have held either way; this is the "coordinate with how DANDER-10
  serializes the nested source config" note in the Design, applied.
- **`SENSITIVE_PARAM_NAMES`** is not enumerated in the Design (only `SENSITIVE_HEADER_NAMES` is
  spelled out); chose a documented, reasonable set (`api_key`/`apikey`/`access_token`/`auth_token`/
  `token`/`secret`/`client_secret`/`password`, plus hyphenated variants), all lowercase,
  case-insensitive match — consistent with the header set's treatment and documented in both the
  module docstring and the README.
- **`README.md`** gained a short *Typed per-node-type config* section documenting DANDER-10 in
  addition to the *Source request/payload spec* section this ticket's Design explicitly asked for:
  DANDER-10 never added README coverage (verified by grep — no `node_config`/`NodeType`/
  `SourceNodeConfig` mentions existed before this change), and the request-spec section reads as a
  non sequitur without at least a paragraph on the typed-config model it attaches to. Kept minimal
  and factual; flagging here rather than silently expanding scope.

Everything else matches the Design section as written: new module
`src/dander/pipeline/request_spec.py` (`HttpMethod`, `SENSITIVE_HEADER_NAMES`/
`SENSITIVE_PARAM_NAMES`, `is_secret_reference`/`is_field_reference`/`is_reference`/
`looks_like_raw_credential`, `RequestSpec` with its `_check_reference_values` model validator
applying Rule A to sensitive-named headers/params and Rule B to every string leaf of headers,
params, and body); `SourceNodeConfig` gains `request: RequestSpec | None = None`;
`src/dander/pipeline/__init__.py` exports `HttpMethod`/`RequestSpec`; new
`tests/pipeline/test_request_spec.py` covers a full request spec loading from YAML and JSON,
round-trip stability in both formats, a spec-less source node's backward compatibility (including
the on-disk `request` omission) in both formats, the reference contract (Rule A on a sensitive
header and a sensitive param, Rule B on a plain header and a nested body leaf, a benign literal
passing, no leaked values), and the pure helper functions directly (parametrized across reference
forms, benign literals, and credential-shaped literals).

Toolchain: `uv run ruff check`, `uv run ruff format --check`, and `uv run mypy` (strict, 37
files) all clean on every file this ticket touches. `uv run pytest` — 154 passed, 0 failed (110
baseline + 44 new), no network. The one `ruff format`/`ruff check` finding in the repo
(`scripts/watch_workflows.py`, a pre-existing long line) predates this change and is unrelated —
confirmed via `git stash`, matching the note already on file from DANDER-10.

## Review Log

_Append-only. PR-Review adds entries below._

### 2026-07-23 — PASS

Reviewed the implementation against all seven acceptance criteria, the steering files
(`01-security.md`, `02-engineering.md`, `languages/python.md`), and the approved Design.

**Acceptance criteria — all met:**

1. Declarative request-spec model (`RequestSpec` in `src/dander/pipeline/request_spec.py`):
   closed `HttpMethod` StrEnum (GET/POST/PUT/PATCH/DELETE), `headers`, `query_params`, and a
   `dict | str | None` `body` template. Fully type-annotated; mypy strict clean.
2. Reference-only contract enforced by `_check_reference_values`: Rule A (deterministic) rejects
   any literal in a sensitive-named header/param position; Rule B (best-effort tripwire) rejects
   credential-shaped literals anywhere, including nested body leaves. Verified directly:
   `Bearer …` in `Authorization` and `sk_live…`/`AKIA…` literals are rejected; benign
   `Content-Type: application/json` passes. Satisfies AC #2's "rejected or explicitly disallowed."
3. Backward compatibility: `request` is optional, defaults to `None`; `method` defaults to `GET`.
   A spec-less source node loads and round-trips, and (bonus) omits `request` on dump rather than
   writing `request: null` — verified in both YAML and JSON tests.
4. Round-trip stability via model equality confirmed for a full spec in **both** YAML and JSON
   (`test_yaml/json_round_trip_is_stable_for_a_full_request_spec`).
5. Google-style docstrings on the module, `RequestSpec`, `HttpMethod`, and every helper state
   values are references only and are never resolved/sent here. Typed per `languages/python.md`.
6. pytest coverage (`tests/pipeline/test_request_spec.py`): YAML+JSON load of method/headers/
   params/body, round-trip in both formats, Rule A on a sensitive header and param, Rule B on a
   plain header and a nested body leaf, benign literal accepted, spec-less backward compat, and
   the pure helpers parametrized. All tokens synthetic; no network.
7. Toolchain green: `uv run ruff check`, `ruff format --check`, `mypy` (strict, 6 pipeline
   source files) all clean; `uv run pytest` 154 passed, 0 failed.

**Security (zero-tolerance):** No hardcoded real secrets in the diff — test tokens are clearly
synthetic (`secret:demo_key`, `field:candidate_id`, fake `Bearer`/`sk_live`/`AKIA` shapes).
`hide_input_in_errors=True` plus value-free error messages confirmed to prevent leaking the
offending literal (verified `leakme` absent from the raised `ValidationError`). No new secret key;
`.env.example` correctly unchanged (references only). No secrets/PII in logs or fixtures.

**Design fidelity:** Matches the approved Design. The three Implementation-Notes deviations are
sound and justified: (1) `looks_like_raw_credential` guards `is_reference` internally so a numeric
Secret-Manager resource name is not misflagged — verified (`projects/1234567890/…/versions/3`
returns `False`); (2) `hide_input_in_errors=True` mirrors DANDER-10's `Node` fix; (3) the
non-`TYPE_CHECKING` `RequestSpec` import with a documented `# noqa: TC001` is required for Pydantic
schema resolution. The in-scope `graph.py` `_dump_graph_payload` extension for `request` omission
mirrors the existing join-less-`join` pattern. README documentation kept true to code.

**Engineering:** Interface-first (helpers are pure, unit-testable in isolation; `RequestSpec` is
inert — no I/O, no secret resolution, no HTTP). No swallowed errors; explicit `ValueError`s with
actionable, value-free context. Stays within scope (model + serialization + validation + tests).

No blocking issues. Status set to `done`.
