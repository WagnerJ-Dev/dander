# Morning Handoff

## Finished

- Added a read-only Salesforce Accounts connector using External Client App JWT authentication,
  QueryAll, opaque response-link pagination, a declared raw schema, and `SystemModstamp` watermark.
- Added the `stg_salesforce__accounts` model and its contract/tests.
- Extended the shared declarative REST layer with JSON-link pagination and configurable JWT
  audience/assertion lifetime while preserving existing provider defaults.
- Documented External Client App setup, secret references, current full-reread/SCD1 boundary, and
  later scale options.
- Proved the connector twice against the disposable Salesforce Developer Edition org.

## Try It

```bash
cp connectors/salesforce_jwt.example.yaml connectors/salesforce.yaml
# After editing the connector, validate configuration only:
uv run dander run salesforce --dry-run --sandbox --project YOUR_NO_BILLING_GCP_PROJECT
# For real authentication/extraction, follow docs/salesforce.md and omit --dry-run.
```

## Checks

- Live JWT proof: 13 Accounts; duplicate-free replay, retained record envelope, and stable watermark.
- Full suite: 610 passed; focused Salesforce tests: 69 passed.
- Ruff lint/format and strict mypy passed.
- Locked dependency audit: no known vulnerabilities.
- Terraform formatting and both backend-disabled validations passed; no apply or GCP mutation ran.
- Wheel/sdist inspection, Docker build, container CLI, and packaged Salesforce template checks
  passed.

## Decisions

- Accounts are the first complete Salesforce slice; source writes are out of scope.
- QueryAll fully rereads this bounded initial slice; hosted SCD1 publication keeps replay idempotent.
- External Client App JWT uses the `api` and required `refresh_token/offline_access` scopes, but
  Dander neither receives nor stores refresh tokens.

## Remaining

- Add the connector to a hosted manifest and apply only under separate GCP approval.
- Add timestamp-filtered SOQL or Bulk API 2.0 only when Salesforce volume requires it.

## Review First

- `connectors/salesforce_jwt.example.yaml`
- `src/dander/security/oauth_jwt.py` and `src/dander/ingestion/pagination.py`
- `tests/test_runtime.py` and `models/staging/stg_salesforce__accounts.yml`
