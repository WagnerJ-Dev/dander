# Salesforce Accounts

Dander's first Salesforce slice is intentionally read-only: one Accounts QueryAll extraction,
opaque response-link pagination, declared raw schema, SCD1 publication, one staging model, and the
existing transform/test/run-history path. It does not modify Salesforce records.

Salesforce restricts creation of legacy Connected Apps as of Spring '26 and recommends External
Client Apps for new integrations. Configure one External Client App for non-interactive JWT bearer
authentication:

1. Generate a 2048-bit RSA private key and self-signed public certificate outside the repository.
2. In **Setup → External Client App Manager**, create a local app and enable OAuth.
3. Add **Manage user data via APIs (`api`)** and **Perform requests at any time
   (`refresh_token`, `offline_access`)**, enable **JWT Bearer Flow**, and upload only the public
   certificate. Salesforce requires the refresh-token scope when an External Client App uses this
   preauthorized JWT flow; Dander does not store or use a refresh token.
4. Set permitted users to **Admin approved users are pre-authorized**, select a narrow permission
   set that can read Account and the selected fields, and assign it to the JWT subject user.
5. Copy the consumer key. Store it and the private key as secret values; never place either value
   in connector YAML.

Copy and edit the template:

```bash
cp connectors/salesforce_jwt.example.yaml connectors/salesforce.yaml
```

Replace `YOUR_DOMAIN`, the API version when necessary, and the JWT `subject`. Production orgs use
`https://login.salesforce.com` as both authorization-server audience and token host; sandboxes use
`https://test.salesforce.com`. My Domain hosts are also supported when both values follow the org's
OAuth configuration.

First validate the connector shape without resolving secrets or contacting Salesforce:

```bash
uv run dander run salesforce --dry-run --sandbox --project YOUR_NO_BILLING_GCP_PROJECT
```

That command is configuration-only; it does not prove authentication. For a real local extraction,
authenticate Application Default Credentials to a BigQuery Sandbox GCP project with billing
disabled, then resolve the template's two references from environment variables and omit
`--dry-run`:

```bash
gcloud auth application-default login
export SALESFORCE_EXTERNAL_CLIENT_APP_ID='the-consumer-key'
export SALESFORCE_EXTERNAL_CLIENT_APP_PRIVATE_KEY="$(< /secure/path/dander-salesforce.key)"
uv run dander run salesforce --sandbox --project YOUR_NO_BILLING_GCP_PROJECT
```

The caller must be able to read the project's billing status and create/write the BigQuery Sandbox
dataset. The real command authenticates to Salesforce, extracts Accounts, replaces the raw sandbox
table, and records local run/cursor state in `.dander/state.db`.

A hosted pipeline should map those same environment names to two Secret Manager containers in
`dander.yaml`; Terraform manages the containers and least-privilege runtime access, not secret
versions. Review the plan before applying.

## Current boundary

The connector follows every `nextRecordsUrl` and sees soft-deleted Accounts through QueryAll. It
records the maximum `SystemModstamp`, but the initial slice intentionally rereads the endpoint
instead of rewriting SOQL around a stored timestamp. Hosted SCD1 merge makes replays idempotent.
Large orgs that need server-filtered SOQL or Bulk API 2.0 should treat those as later scale work.

Official Salesforce references:

- [External Client Apps](https://developer.salesforce.com/docs/platform/mobile-sdk/guide/eca-create.html)
- [OAuth JWT bearer flow](https://help.salesforce.com/s/articleView?id=xcloud.remoteaccess_oauth_jwt_flow.htm&type=5)
- [Processing query results and `nextRecordsUrl`](https://developer.salesforce.com/blogs/2022/12/processing-large-amounts-of-data-with-apis-part-1-of-2)
