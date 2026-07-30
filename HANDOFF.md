# Morning Handoff

## Finished

- Audited every live upstream architecture requirement against concrete code and tests.
- Enforced configured token-bucket pacing and bounded safe-read retries on dlt sources.
- Added Marketo-compatible OAuth credential placement and a no-secret connector template.
- Fixed the deployable image context so connector and transform assets are present.
- Classified every module as locally implemented while preserving external release gates.

## Try It

Run `uv run dander --help`. For Marketo, copy `connectors/marketo.example.yaml` to an ignored/local
connector, replace `MUNCHKIN_ID`, and supply only the named environment or Secret Manager refs.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed across 88 source files.
- `uv run pytest` — 431 passed.
- Terraform formatting and validation — passed.
- Wheel install/CLI and local amd64 Docker image artifact checks — passed.

## Decisions

- dlt retries only GET/HEAD and never mutating requests.
- Marketo token credentials use its documented query placement; API tokens use bearer headers.
- “Implemented locally” never implies provider, billing, production, or legal approval.

## Remaining

- Obtain upstream-required OSS/legal approval before customer-data release.
- Run Marketo and enterprise tenant integrations when credentials are available.
- Run hosted, Dataplex, and Storage Write proofs only with explicit cost authorization.
- Stream/spool very large endpoint extracts instead of holding a logical batch in memory.
- Add nested/repeated schema evolution only from explicit reviewed contracts.

## Review First

- `docs/release-audit.md`
- `src/dander/ingestion/dlt_backed.py`
- `src/dander/security/oauth.py`
