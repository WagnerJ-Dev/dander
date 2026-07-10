# Security Steering — NON-NEGOTIABLE

> Every agent MUST read and obey this before writing code. Violations are automatic PR-review
> failures. This is a data platform touching HR/comp and customer data — security is the product.

## 1. Secrets: zero hardcoding, ever

- **NEVER** write a secret, key, password, token, connection string, or credential literal into
  source, config, tests, fixtures, comments, or commit messages. Not even a placeholder that
  looks real. Not even "temporarily."
- All secrets come from, in order of preference:
  1. **GCP Secret Manager**, referenced by resource name (`projects/…/secrets/NAME/versions/latest`).
  2. **Environment variables** (loaded from `.env` locally).
- `.env` is git-ignored. `.env.example` (keys only, empty values) IS committed and kept in sync.
- If you need a new secret, add its **key** to `.env.example` and reference it in `steering`/docs —
  never its value.
- Config files reference secrets **indirectly**: store the Secret Manager resource name or the
  env var *name*, never the value.

## 2. Auth is a strategy, not a special case

The named systems do not share an auth model, so auth is a **pluggable strategy** behind one
interface (`get_credentials(system_name)`):

| System | Strategy |
|---|---|
| Salesforce | OAuth2 (JWT bearer / connected-app) |
| Workday | SOAP/RaaS basic-auth, or REST OAuth2 + cert |
| NetSuite | OAuth 1.0a token-based (TBA) |
| Greenhouse (Harvest) | API key over basic auth |
| Marketo | OAuth2 client credentials |
| Xactly | hand-rolled (niche) |

Concrete strategies (`OAuth2ClientCredentials`, `OAuth2JWT`, `OAuth1TBA`, `ApiKeyBasic`, …)
implement the interface. Never bake one system's auth into shared code.

## 3. Credential access is audited

Every credential fetch logs **who/what/when/which-secret** (not the value). Build this into the
Security Module from day one — a financial company will ask "who accessed what credential when."

## 4. Least privilege & identity

- Cloud compute uses **Workload Identity Federation** — no long-lived service-account key files
  in the cloud. Key files are local-dev only and always git-ignored.
- Service accounts get the **minimum** IAM roles needed; prefer predefined narrow roles over
  broad ones; never `owner`/`editor` for runtime identities.

## 5. Data sensitivity

- Treat all ingested data as sensitive by default (HR/comp/customer/PII). No sensitive data in
  logs, error messages, test fixtures, or sample payloads committed to the repo.
- When inferring/sampling schemas, scrub values before persisting anything to the repo.

## 6. Terraform state

- State can contain secrets — use a **remote GCS backend**, never local state in the repo.
- No secret values in `.tf` or `.tfvars`. Reference Secret Manager; commit only `*.tfvars.example`.

## 7. Dependencies

- Pin dependencies. Prefer well-maintained libraries; review new third-party deps for the code
  they run at install/runtime. Flag anything that phones home.

## Quick self-check before any commit

- [ ] No literal secret anywhere in the diff (grep the diff for keys/tokens/passwords).
- [ ] New secret keys added to `.env.example` (names only).
- [ ] No sensitive data in logs, fixtures, or sample data.
- [ ] Runtime identity uses WIF + least-privilege IAM.
