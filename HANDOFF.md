# Morning Handoff

## Finished

- Added a loopback-only synthetic SaaS API with entirely invented records.
- Added cursor and Link-header endpoints with duplicates and incremental updates.
- Added deterministic 429/500 recovery through the real rate-limited dlt HTTP adapter.
- Added the packaged `dander-synthetic-api` command and matching connector.
- Documented the local proof boundary and its provenance decision.

## Try It

Run `uv run dander-synthetic-api`, then in another terminal run
`uv run dander run synthetic_vendor --dry-run --project local-demo`. Run the live-local proof with
`uv run pytest tests/ingestion/test_synthetic_vendor.py`.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed across 91 source files.
- `uv run pytest` — 433 passed.
- Terraform recursive formatting and root validation — passed.
- Synthetic connector CLI dry run — passed with two SCD1 targets.
- Secret-pattern and diff checks — no new secret or whitespace issue.

## Decisions

- The default REST integration proof uses only invented loopback data.
- The synthetic server proves extraction; the normal CLI retains its explicit BigQuery write path.
- No scheduler, billing, GCP resource, deployment, or public remote was changed.

## Remaining

- Decide whether to leave the daily 09:00 Cloud Scheduler run enabled.
- Run Marketo and enterprise tenant integrations when credentials are available.
- Run hosted, Dataplex, and Storage Write proofs only with explicit per-run cost approval.
- Stream/spool very large endpoint extracts instead of holding a logical batch in memory.
- Add nested/repeated schema evolution only from explicit reviewed contracts.

## Review First

- `src/dander/dev/synthetic_vendor.py`
- `tests/ingestion/test_synthetic_vendor.py`
- `connectors/synthetic_vendor.yaml`
