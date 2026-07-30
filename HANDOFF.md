# Morning Handoff

## Finished

- Kept Greenhouse as the primary real public demo.
- Added credential-free Lever and Ashby job-board connectors.
- Proved Lever offset pagination and Ashby's enveloped response against their live APIs.
- Added typed non-secret query parameters with credential-name rejection.
- Kept synthetic data exclusively for deterministic duplicates, updates, 429s, and 500s.

## Try It

Run `uv run dander run lever_job_board --dry-run --project local-demo` and
`uv run dander run ashby_job_board --dry-run --project local-demo`. Their offline contracts are in
`tests/ingestion/test_public_job_connectors.py`.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed across 92 source files.
- `uv run pytest` — 439 passed.
- Terraform recursive formatting and root validation — passed.
- Live Lever extraction — 104 rows/104 unique ids; live Ashby — 58/58.
- Both connector CLI dry-run plans — passed with SCD1 targets.

## Decisions

- Public ATS records prove real provider shapes; synthetic records prove controlled failures.
- Static query parameters cannot carry credential-like names.
- Candidate/contact tests use invented records in an owned test account, never public profiles.

## Remaining

- Decide whether to leave the daily 09:00 Cloud Scheduler run enabled.
- Connect a free HubSpot developer test account only after its owner authorizes an app.
- Run Marketo and enterprise tenant integrations when credentials are available.
- Run hosted, Dataplex, and Storage Write proofs only with explicit per-run cost approval.
- Stream/spool very large endpoint extracts and review nested/repeated schema evolution.

## Review First

- `connectors/lever_job_board.yaml`
- `connectors/ashby_job_board.yaml`
- `src/dander/ingestion/source.py`
