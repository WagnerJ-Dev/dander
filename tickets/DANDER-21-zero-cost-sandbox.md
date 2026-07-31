# DANDER-21 — Zero-cost BigQuery sandbox mode

Status: done

## Context

BigQuery Sandbox works without a billing account, but does not support DML. Dander's production
writer uses `MERGE`, its production state store uses DML, and Terraform requires services outside
the strict no-billing boundary.

## Acceptance criteria

- `dander run --sandbox` fails closed unless Cloud Billing reports billing is disabled.
- Sandbox mode skips Terraform, Secret Manager, and BigQuery DML.
- Tables are replaced through BigQuery load jobs and empty extracts remove stale tables.
- Each run is a full refresh; local SQLite records the last observed cursor for diagnostics only.
- The sandbox dataset is created through the BigQuery API when absent.
- Production SCD1 and BigQuery watermark behavior remain unchanged.
- Tests use fakes and make no GCP or source-network calls.
- README, architecture decisions, and handoff explain the limitations and usage.

## Review

PASS — billing verification precedes dataset creation and accepts only an explicit boolean false;
the sandbox writer emits no SQL/DML; full refresh and local state behavior are independently
tested; production composition is unchanged. Ruff, formatting, strict mypy, 301 tests, CLI help,
and sandbox dry-run smoke checks pass.
