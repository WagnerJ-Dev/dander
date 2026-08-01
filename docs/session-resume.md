# Session Resume — 2026-08-01

Read `HANDOFF.md`, `docs/decisions.md`, `docs/spec-alignment.md`, and
`docs/release-audit.md` before changing code or cloud resources.

## Git state

- Repository: `/Users/harrison/Documents/dander`.
- Working branch: `main`; local and `origin/main` are synchronized.
- PR #10 merged the tracked HubSpot schedule and operator-private Cloud Monitoring failure
  delivery; PR #11 finalized this handoff. Their feature branches were removed locally and from
  GitHub.

## Live project

- Project `dander-proof-harrison-20260801`, region `us-central1`, remote states
  `dander/state` and `dander/bootstrap-admin/state` in
  `dander-proof-harrison-20260801-dander-state`.
- Greenhouse is enabled at 09:00 ET; HubSpot is enabled at 10:00 ET. Both jobs retain immutable
  digest `sha256:538f1af2…9fbd4`; the simulation-only USD 5 cost guard is unchanged.
- Secret `hubspot-private-app-token` has enabled version 1 and is accessible only to
  `dander-runtime-hubspot`. The test app intentionally keeps company read/write scopes.
- One synthetic company, `dander-integration-sandbox.invalid`, is retained so the current writer
  can bootstrap the nested raw table from a non-empty first batch.

## HubSpot proof

- Empty-account canary failed before transformation because zero extraction did not create
  `raw.hubspot_test_companies`; no credential failure occurred.
- Recovery execution `dander-hubspot-companies-ltzhd` / run
  `46f74635ca26442ab5a7ad4ea92660e7` and replay `-5vvwd` / run
  `53cd93774a8a42929374d51753e76b43` succeeded.
- Each successful run extracted/affected one row, built one model, passed three assertions, and
  published one schema-v2 asset. Raw/staging remain one row; stable hash is
  `e9f22b28edd5cea6dca4211f6fb82166407761c3e6c980056e1d2f15072f4350`.

## Alerting and reconciliation

- Email channel `6736670643697224971` is enabled. Alert policies `6338652023037311338`
  (Greenhouse) and `3086813104792953319` (HubSpot) each filter exact-job failed executions.
- Controlled no-data-mutation execution `dander-hubspot-companies-mnfxq` failed after one retry and
  opened incident `0.oaxg8wnfqgc7`; HubSpot/BigQuery state stayed unchanged.
- Both administrative and platform Terraform follow-up plans returned `No changes`.

## Safety boundaries

- Repeat `--failure-alert-email` on every future `dander init` reconciliation; the recipient is
  deliberately absent from public `dander.yaml`.
- Do not delete the seed, rotate or expose the token, change scopes, make the cost guard live,
  publish Dataplex, or alter schedules without explicit approval.
