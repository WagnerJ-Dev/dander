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
