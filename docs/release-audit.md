# Dander Platform Release Audit

Audited on 2026-07-31 against the product promise in `steering/00-project-overview.md`. “Live-proven” means the behavior was observed in the dedicated GCP sandbox. “Implemented” means the checked-in implementation and automated tests cover the contract, but a deliberately billable or credential-dependent provider operation remains outside this proof.

## Requirement evidence

| Product requirement | Status | Authoritative evidence |
|---|---|---|
| One CLI and typed project manifest | Live-proven | `dander.yaml` declares additive Greenhouse and HubSpot pipelines; `dander validate` passes; the explicit `dander init` upgrade command produced a saved `No changes` plan against the real remote state. |
| Batteries-included infrastructure | Live-proven in the retained sandbox | The read-only verifier passes for the GCS backend, four BigQuery datasets, immutable Cloud Run jobs, Scheduler jobs, per-runtime IAM, billing-account viewer bindings, and the HubSpot Secret Manager container. The complete clean-project orchestration is covered by bootstrap tests; a new-project apply remains separately approval-gated. |
| Additive multi-pipeline hosting | Live-proven | Greenhouse remains `dander-greenhouse-public` with an enabled scheduler; HubSpot is `dander-hubspot-companies` with a paused scheduler. Each uses distinct runtime and scheduler identities. |
| Resource-scoped SaaS credentials | Live-proven | `hubspot-private-app-token` grants `roles/secretmanager.secretAccessor` only to `dander-runtime-hubspot`; Greenhouse has no secret binding. Secret values are absent from Terraform and evidence. |
| Ingestion and idempotent BigQuery writes | Live-proven | Greenhouse execution `dander-greenhouse-public-nm8wg` extracted/affected 21 rows. HubSpot’s controlled initial/update/replay proof passed with stable replay hashes and watermarks; its synthetic companies were deleted afterward. |
| Owned transform engine and tests | Live-proven | Both hosted executions built one staging model and passed three declared assertions through the shared executor. Raw/staging retain 25/25 Greenhouse rows and 4/4 HubSpot rows. |
| Durable run lifecycle | Live-proven | `dander_meta._dander_runs` contains terminal `complete/succeeded` rows for pipeline IDs `greenhouse_jobs` and `hubspot_companies`, including stage counts and failure-stage fields. |
| Single metadata spine and semantic registry | Live-proven | `dander_meta._dander_catalog` atomically stores one schema-v2 snapshot per pipeline. `dander metadata` exposes sources, columns, upstream relations, tests, runs, and governed metrics `published_job_count` and `proof_company_count`. |
| Infrastructure reconciliation safety | Live-proven | The post-deployment Terraform detailed-exitcode plan returned 0 (`No changes`). No job was replaced, Greenhouse scheduling stayed enabled, and HubSpot stayed paused. |
| Broader connector/auth/writer library | Implemented | Automated coverage retains REST/dlt and Workday paths, API/basic/OAuth2/OAuth1 strategies, SCD1/SCD2/snapshot/incremental writers, bounded load jobs, and Storage Write request semantics. |
| Optional Dataplex projection | Implemented | Deterministic aspect generation and publisher/read-back logic are tested. No live Dataplex mutation is claimed because it is optional and may be billable. |

## Live execution record

- Runtime manifest digest: `sha256:a4ec1a3eca1e4c3963ea461c9134ddc1d4d00b134fd30c2f13c4c57805962289`.
- Greenhouse: Cloud Run execution `dander-greenhouse-public-nm8wg`; Dander run `2441c4843aab418fb9d6e9523eb9b0c2`; 21 extracted, one model, three tests, one catalog asset.
- HubSpot: Cloud Run execution `dander-hubspot-companies-l2g6c`; Dander run `6e3258bc0eab4a47ad1bfeae38704912`; source access succeeded, one model, three tests, one catalog asset.
- Sanitized deployment summaries are under ignored `evidence/platform-greenhouse` and `evidence/platform-hubspot`.

## Release boundaries

- Dander does not create or billing-link a GCP project; `dander init` provisions the platform inside an existing project. Creating a separate clean proof project requires explicit approval and a retained teardown or inventory record.
- The USD 5 budget guard is simulation-first and does not mathematically cap delayed cloud charges.
- HubSpot’s schedule remains paused; enabling unattended vendor access is an operator decision.
- Live Storage Write, private enterprise tenants, and optional Dataplex publication are not implied by the two hosted pipeline proofs.

## Verdict

The repository and retained sandbox now demonstrate the promised vertical slice: one manifest and CLI provision/reconcile additive hosted pipelines, ingest and transform through one executor, and persist an inspectable metadata/run spine. The remaining clean-project and Dataplex items are external release proofs, not missing core implementation.
