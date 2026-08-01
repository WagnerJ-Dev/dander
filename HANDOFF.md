# Morning Handoff

## Finished

- Connected the dedicated HubSpot account through Secret Manager and retained approved company read/write scopes.
- Proved hosted HubSpot recovery and replay: one raw/staging row, one model, three assertions, one schema-v2 asset, and identical content hashes.
- Enabled HubSpot daily at 10:00 ET alongside Greenhouse at 09:00 ET; both jobs retained the same immutable image.
- Added operator-private email failure delivery with one exact-job Cloud Monitoring policy per pipeline.
- Opened a real HubSpot failure incident without mutating HubSpot or BigQuery; both Terraform roots then returned `No changes`.

## Try It

- Run `uv run dander metadata runs --project dander-proof-harrison-20260801`.
- Inspect Cloud Scheduler and Monitoring in `dander-proof-harrison-20260801`; both schedules and alert policies are enabled.

## Checks

- Recovery `dander-hubspot-companies-ltzhd` and replay `-5vvwd` succeeded; Dander runs `46f74635…` and `53cd9377…` each completed all stages.
- Raw/staging counts remain 1; both replay hashes are `e9f22b28…f4350`; catalog schema is v2 with one HubSpot asset.
- Controlled failure `dander-hubspot-companies-mnfxq` opened incident `0.oaxg8wnfqgc7`; pipeline data and last successful run stayed unchanged.
- Full gate: 500 tests, Ruff lint/format, strict mypy across 119 files, Terraform formatting, and both root validations pass.
- Live administrative and platform follow-up plans: `No changes`.

## Decisions

- Keep one clearly synthetic seed company to work around the generic empty-first-batch raw-schema limitation.
- Keep approved read/write scopes because this HubSpot account is disposable and testing-only.
- Keep the private alert recipient outside `dander.yaml`; future reconciliations must repeat `--failure-alert-email`.

## Remaining

- Teach the writer to create declared nested raw schemas for empty first batches, then remove the seed workaround if desired.
- Confirm the smoke notification arrived in the configured inbox; the Cloud Monitoring incident is already open.
- Storage Write, WIF artifact upload, and optional Dataplex remain separate proofs.

## Review First

- `infra/modules/scheduled-job/main.tf`
- `src/dander/bootstrap/terraform.py`
- `docs/release-audit.md`
