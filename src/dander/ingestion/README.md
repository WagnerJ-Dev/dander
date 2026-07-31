# Hybrid ingestion

Dander has two concrete paths behind the same `Source` contract:

- `DltRestSource` translates ordinary declarative REST connectors into dlt resources.
- `WorkdayRaasSource` owns the request loop for Workday RaaS reports: OAuth/basic auth strategy
  application, response-envelope selection, page-number pagination, cursor params, bounded
  rate-limit backoff, and explicit BigQuery scalar casts.

Set `engine: workday_raas` in connector YAML to select the hand-rolled path. Its HTTP transport and
sleeper are injected seams, so the full behavior is testable without a tenant or credential.
`discover()` reports declarations only and never samples employee rows.

Enterprise casts currently cover `BOOL`, `DATE`, `FLOAT64`, `INT64`, `NUMERIC`, `STRING`, and
timezone-aware `TIMESTAMP`. Cast errors name only the endpoint/field/type contract, never values.
Automatic nested-record schema evolution remains separate work.

## Synthetic vendor proof

Run `uv run dander-synthetic-api` to start an entirely local, credential-free SaaS facsimile on
`127.0.0.1:8765`. The matching `connectors/synthetic_vendor.yaml` exercises JSON cursor and
Link-header pagination, duplicate business keys, incremental updates, and bounded recovery from a
deterministic 429 and 500. The integration tests call it over real HTTP; no vendor tenant or cloud
resource is involved.

Greenhouse is the primary live public demo. The `lever_job_board` connector adds real published
jobs with offset pagination, and `ashby_job_board` adds a second real ATS response envelope. Their
offline tests pin request construction; live data counts are deliberately not asserted because
public postings change. Static `query_params` may configure non-secret response options, while
credential-like parameter names fail validation and must be handled by `auth_strategy`.
