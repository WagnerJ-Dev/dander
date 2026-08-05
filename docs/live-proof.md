# Manual live proof

The `Live proof` workflow is manual, protected by the `live-proof` GitHub environment, and the only automated path authorized to mutate a billing-linked proof project. It never creates a GCP project or links billing.

## Stage-zero prerequisite

Use a disposable, billing-linked project. Before the first workflow run, an approved administrator must create only the state bucket, bootstrap identity, Artifact Registry repository, and repository/ref-scoped Workload Identity Federation resources with `dander init-admin-plan` and `dander init-admin-apply`. Store these non-secret environment variables:

- `DANDER_WIF_PROVIDER` — full Workload Identity Federation provider resource name.
- `DANDER_WIF_SERVICE_ACCOUNT` — stage-zero GitHub service-account email.

The workflow inputs identify that same project, state bucket, bootstrap service account, and billing account. No service-account key file is allowed.

For an interactive clean-project proof instead, an approved `gcloud` administrator can run the single `dander init --project ... --billing-account ... --apply` command documented in the README; that path owns stage zero, image publication, and platform apply itself.

That interactive path began on 2026-08-01 in `dander-proof-harrison-20260801`. The retained project
now has five separately deployed pipelines: four daily connector pipelines and one paused
executable graph. Current schedule, image, and interface state is recorded in
`docs/session-resume.md`. The cost guard remains simulation-only, and retained resources must not
be deleted or changed merely to repeat a proof.

## Safety and proof behavior

The workflow derives `dander.live-proof.yaml` from the tracked manifest and forces every declared
pipeline schedule to `paused: true`. With the current manifest, its Terraform plan therefore
contains all five pipelines and their supporting resources. The repository proof manifest uses
Dander's built-in connector implementations, not the separately published plugin packages. The
workflow directly verifies the Greenhouse and HubSpot deployments, executes Greenhouse manually,
and can optionally run the controlled HubSpot, Storage Write, or Dataplex proof. It does not
directly execute or validate the Salesforce, ServiceNow, or executable-graph pipelines; those
require their own bounded acceptance records.

Add `HUBSPOT_PRIVATE_APP_TOKEN` only as a protected environment secret. When the authenticated proof is selected, the workflow adds a secret version only after Terraform has created its container, then creates, updates, validates, and removes invented companies. The token, payloads, Terraform state, and raw provider responses are never retained.

Dataplex publication is disabled by default and scoped to the selected proof pipeline when explicitly enabled. The cost guard remains simulation-first. All schedules remain paused after the workflow.

## Evidence and retention

Every run uploads a sanitized evidence bundle even after failure. It includes:

- the commit, workflow run, Terraform plan hash, and immutable image digest;
- Greenhouse and HubSpot deployment summaries and the canonical proof results;
- an always-run retained-resource inventory covering state, datasets, jobs, schedules, service accounts, secrets, and Artifact Registry.

The inventory records state only; it never deletes resources. Review `manifest.json`, both deployment summaries, and `teardown.json` before completing the proof ticket. Never attach raw logs, Terraform state, source rows, billing responses, or credentials to a pull request.
