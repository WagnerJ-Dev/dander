# Morning Handoff

## Finished

- Added generic OAuth2 JWT bearer authentication with RSA signing and token caching.
- Added RFC 5849 OAuth1 TBA with NetSuite's HMAC-SHA256 profile.
- Wired both strategies through connector validation and CLI dispatch.
- Added credential-free Salesforce JWT and NetSuite TBA connector templates.
- Proved real RSA claim signing and deterministic OAuth1 signatures offline.

## Try It

Copy `connectors/salesforce_jwt.example.yaml` or `connectors/netsuite.example.yaml`, replace
account identifiers and secret reference names, then run `uv run dander run NAME --dry-run`.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed across 83 source files.
- `uv run pytest` — 406 passed.
- `git diff --check` — passed.
- Secret-pattern scan found only its intentional private-key detector fixture.

## Decisions

- JWT tokens use provider expiry or a conservative 300-second default.
- OAuth1 resolves all credentials per request and signs query parameters deterministically.
- Templates contain references only; no credentials or generated key material are committed.

## Remaining

- Revise and execute the join graph shape.
- Add bounded writer loads and controlled nested schema evolution.
- Add hosted transform/catalog scheduling and run history.
- Complete the release audit and external legal gate.

## Review First

- `src/dander/security/oauth_jwt.py`
- `src/dander/security/oauth1.py`
- `docs/spec-alignment.md`
