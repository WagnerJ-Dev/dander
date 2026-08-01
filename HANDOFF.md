# Morning Handoff

## Finished

- Created the `Dander BigQuery Pipeline` private app in HubSpot sandbox portal `246915065` with only company read/write scopes.
- Stored the access token as enabled Secret Manager version 3 in `hubspot-private-app-token`; invalid versions 1 and 2 are disabled, and only the Dander runtime service account has accessor permission.
- Reconfigured the existing hosted job in place for `hubspot_test` plus `stg_hubspot__companies`, with the daily scheduler paused.
- Passed the controlled initial/update/replay proof and removed both synthetic HubSpot companies afterward.

## Try It

- Inspect the sanitized proof at `evidence/hubspot-20260731/authenticated-ingestion.json` (local and intentionally ignored).
- Run the job manually with `gcloud run jobs execute dander-greenhouse-public --project=dander-sbx-harrison-20260729 --region=us-central1 --wait`.

## Checks

- Targeted CLI, bootstrap, ingestion, and security tests passed: 29 passed.
- Three Cloud Run executions completed successfully; the proof recorded passed update, idempotency, and watermark assertions.
- BigQuery contains 2 raw rows and 2 staging rows, with 2 unique company IDs and 1 observed update.
- Both temporary HubSpot company IDs return 404 after cleanup.
- Final Terraform plan returned exit code 0 with no changes; scheduler state is `PAUSED`.

## Decisions

- Used the existing private-app bearer-token connector path; HubSpot marks legacy private apps as limited and recommends Service Keys for future work.
- Granted write scope only so controlled proof data could be created and removed.
- Kept the scheduler paused after proof to prevent unattended sandbox writes.

## Remaining

- Decide whether HubSpot should receive its own renamed Cloud Run job instead of reusing `dander-greenhouse-public`.
- Enable scheduling only after choosing the intended production HubSpot account and cadence.
- Migrate from the legacy private app to HubSpot Service Keys when Dander supports that authentication flow.

## Review First

- `connectors/hubspot_test.yaml`
- `models/staging/stg_hubspot__companies.sql`
- `scripts/live_proof/hubspot.py`
