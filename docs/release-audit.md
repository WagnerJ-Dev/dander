# Dander Platform Release Audit

Audited on 2026-08-01 against the product promise in `steering/00-project-overview.md`. “Live-proven” means the behavior was observed in the retained sandbox or the approved clean proof project. “Implemented” means automated tests cover the contract while a credential-dependent or optional provider operation remains outside this proof.

## Requirement evidence

| Product requirement | Status | Authoritative evidence |
|---|---|---|
| One CLI and typed project manifest | Live-proven | `dander.yaml` declares additive Greenhouse and HubSpot pipelines; `dander validate` passes; the explicit `dander init` upgrade command produced a saved `No changes` plan against the real remote state. |
| Batteries-included infrastructure | Live-proven from a clean project | One approved `dander init --apply` created/adopted remote state, administrative IAM, Artifact Registry, four datasets, both jobs/schedulers, Secret Manager, and the simulation-first cost guard in `dander-proof-harrison-20260801`. |
| Additive multi-pipeline hosting | Live-proven | Greenhouse and HubSpot coexist as separate jobs with distinct runtime/scheduler identities. Both clean-project schedulers remain paused; the retained sandbox keeps its prior Greenhouse-enabled/HubSpot-paused policy. |
| Resource-scoped SaaS credentials | Live-proven | `hubspot-private-app-token` grants `roles/secretmanager.secretAccessor` only to `dander-runtime-hubspot`; Greenhouse has no secret binding. Secret values are absent from Terraform and evidence. |
| Ingestion and idempotent BigQuery writes | Live-proven | Clean-project Greenhouse extracted/affected 21 rows on three successful runs; replay retained 21 rows with identical stable hashes. The sandbox HubSpot initial/update/replay proof also passed and removed its synthetic companies afterward. |
| Owned transform engine and tests | Live-proven | Every clean-project Greenhouse run built one staging model and passed three declared assertions; the sandbox Greenhouse and HubSpot jobs demonstrate the same shared executor. |
| Durable run lifecycle | Live-proven | `dander_meta._dander_runs` contains terminal `complete/succeeded` rows for pipeline IDs `greenhouse_jobs` and `hubspot_companies`, including stage counts and failure-stage fields. |
| Single metadata spine and semantic registry | Live-proven | `dander_meta._dander_catalog` atomically stores one schema-v2 snapshot per pipeline. `dander metadata` exposes sources, columns, upstream relations, tests, runs, and governed metrics `published_job_count` and `proof_company_count`. |
| Infrastructure reconciliation safety | Live-proven | The clean-project post-deployment `dander init` plan returned `No changes`; both schedulers remained paused. The retained sandbox upgrade plan also remains idempotent. |
| Approval-gated release proof | Live-proven interactively | The approved clean-project run used an all-paused manifest, verified both jobs before and after execution, preserved sanitized proof files, and recorded a non-deleting inventory. The WIF workflow remains available but was not dispatched. |
| Broader connector/auth/writer library | Implemented | Automated coverage retains REST/dlt and Workday paths, API/basic/OAuth2/OAuth1 strategies, SCD1/SCD2/snapshot/incremental writers, bounded load jobs, and Storage Write request semantics. |
| Optional Dataplex projection | Implemented | Deterministic aspect generation and publisher/read-back logic are tested. No live Dataplex mutation is claimed because it is optional and may be billable. |

## Live execution record

- Clean project: `dander-proof-harrison-20260801`; immutable image `sha256:d81d865a41ec6da90a251574dfc37d7bf33d98e201f1bdc881c7cf665ef4c125`.
- Clean Greenhouse executions: `dander-greenhouse-public-8x9j9`, `-9ndj6`, and `-g77d2`; Dander runs `6363656f…`, `67f848df…`, and `8b7d1c84…`; each extracted/affected 21 rows, built one model, passed three tests, and published one asset.
- Clean evidence: ignored `evidence/clean-project-20260801`; bootstrap, cost guard, transforms/replay, and retained inventory are `passed`; authenticated HubSpot, Storage Write, WIF IAM, and Dataplex are explicitly `skipped`.
- Runtime manifest digest: `sha256:a4ec1a3eca1e4c3963ea461c9134ddc1d4d00b134fd30c2f13c4c57805962289`.
- Greenhouse: Cloud Run execution `dander-greenhouse-public-nm8wg`; Dander run `2441c4843aab418fb9d6e9523eb9b0c2`; 21 extracted, one model, three tests, one catalog asset.
- HubSpot: Cloud Run execution `dander-hubspot-companies-l2g6c`; Dander run `6e3258bc0eab4a47ad1bfeae38704912`; source access succeeded, one model, three tests, one catalog asset.
- Existing-sandbox deployment summaries remain under ignored `evidence/platform-greenhouse` and `evidence/platform-hubspot`.

## Release boundaries

- Dander does not create or billing-link a GCP project; `dander init` provisions the platform inside an existing project. The approved clean proof project and its inventoried resources are intentionally retained.
- The USD 5 budget guard is simulation-first and does not mathematically cap delayed cloud charges.
- HubSpot’s schedule remains paused; enabling unattended vendor access is an operator decision.
- Live Storage Write, private enterprise tenants, and optional Dataplex publication are not implied by the two hosted pipeline proofs.

## Verdict

The repository, retained sandbox, and clean proof project demonstrate the promised vertical slice: one manifest and CLI provision/reconcile additive hosted pipelines, ingest and transform through one executor, and persist an inspectable metadata/run spine. Authenticated vendor, Storage Write, WIF artifact-upload, and optional Dataplex proofs are deliberately separate from this core claim.
