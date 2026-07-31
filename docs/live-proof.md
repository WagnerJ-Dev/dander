# Manual live proof

The live-proof workflow is intentionally manual and approval-gated. It is the only path that may
use a HubSpot token or mutate a billing-linked proof project.

## GitHub environment

Create a protected environment named `live-proof` and require at least one reviewer. Add these
environment variables from the outputs of `infra/bootstrap-admin`:

- `DANDER_WIF_PROVIDER` — the full Workload Identity Federation provider resource name.
- `DANDER_WIF_SERVICE_ACCOUNT` — the stage-zero GitHub service-account email.

Add the private-app token only as the environment secret `HUBSPOT_PRIVATE_APP_TOKEN`. The token is
used to create, update, and remove invented companies in the owned HubSpot developer test account;
it must never be put in a repository variable, Terraform variable, log, or evidence artifact.

## Proof project

Use a disposable billing-linked project with the simulation-first cost guard. The stage-zero
bootstrap must be configured for the exact repository and the ref from which the manual workflow
will be dispatched. Run the main platform plan and apply through `dander-bootstrap`; do not use a
service-account key file.

Dispatch `.github/workflows/live-proof.yml` with the project id, state bucket, bootstrap service
account, billing account, and only the proof switches you have approved. Keep `teardown_after`
false unless the retained-resource inventory is specifically desired. The workflow always uploads
sanitized evidence, including skipped or failed proof files.

Review `manifest.json` before changing the pull request out of draft. It must identify the commit,
workflow run, Terraform plan hash, immutable image digest, and successful proof statuses. Never
attach raw logs, Terraform state, source rows, billing responses, or credentials to the PR.
