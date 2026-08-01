# Dander Platform Release Audit

Audited on 2026-08-01 against the product promise in `steering/00-project-overview.md`. “Live-proven” means the behavior was observed in the retained sandbox or the approved clean proof project. “Implemented” means automated tests cover the contract while a credential-dependent or optional provider operation remains outside this proof.

## Requirement evidence

| Product requirement | Status | Authoritative evidence |
|---|---|---|
| One CLI and typed project manifest | Live-proven | `dander.yaml` declares additive Greenhouse and HubSpot pipelines; `dander validate` passes; the explicit `dander init` command enables schedules and reconciles failure alerting, with the private recipient supplied only at deploy time. |
| Batteries-included infrastructure | Live-proven from a clean project | One approved `dander init --apply` created/adopted remote state, administrative IAM, Artifact Registry, four datasets, both jobs/schedulers, Secret Manager, and the simulation-first cost guard in `dander-proof-harrison-20260801`. |
| Additive multi-pipeline hosting | Live-proven | Greenhouse and HubSpot coexist as separate jobs with distinct runtime/scheduler identities. The clean-project schedules are independently enabled at 09:00 and 10:00 ET; neither job or immutable image was replaced during HubSpot activation. |
| Resource-scoped SaaS credentials | Live-proven | Secret version 1 of `hubspot-private-app-token` is enabled and grants `roles/secretmanager.secretAccessor` only to `dander-runtime-hubspot`; Greenhouse has no secret binding. The value is absent from Git, Terraform, and evidence. |
| Ingestion and idempotent BigQuery writes | Live-proven | Clean-project HubSpot recovery and replay runs each extracted/affected one synthetic company; raw/staging stayed at one row with identical hash `e9f22b28…f4350`. Greenhouse's earlier three-run replay proof remains intact. |
| Owned transform engine and tests | Live-proven | Every clean-project Greenhouse run built one staging model and passed three declared assertions; the sandbox Greenhouse and HubSpot jobs demonstrate the same shared executor. |
| Durable run lifecycle | Live-proven | `dander_meta._dander_runs` contains terminal `complete/succeeded` rows for pipeline IDs `greenhouse_jobs` and `hubspot_companies`, including stage counts and failure-stage fields. |
| Single metadata spine and semantic registry | Live-proven | `dander_meta._dander_catalog` atomically stores one schema-v2 snapshot per pipeline. `dander metadata` exposes sources, columns, upstream relations, tests, runs, and governed metrics `published_job_count` and `proof_company_count`. |
| Infrastructure reconciliation safety | Live-proven | After schedule activation and alert creation, both administrative and platform Terraform roots returned `No changes`; Greenhouse stayed enabled and both jobs retained digest `sha256:538f1af2…fbd4`. |
| Approval-gated release proof | Live-proven interactively | The approved clean-project run used an all-paused manifest, verified both jobs before and after execution, preserved sanitized proof files, and recorded a non-deleting inventory. The WIF workflow remains available but was not dispatched. |
| Broader connector/auth/writer library | Implemented | Automated coverage retains REST/dlt and Workday paths, API/basic/OAuth2/OAuth1 strategies, SCD1/SCD2/snapshot/incremental writers, bounded load jobs, and Storage Write request semantics. |
| Optional Dataplex projection | Implemented | Deterministic aspect generation and publisher/read-back logic are tested. No live Dataplex mutation is claimed because it is optional and may be billable. |

## Live execution record

- Clean project: `dander-proof-harrison-20260801`; both jobs use immutable image `sha256:538f1af2e62db2ff8fb908766b04adc8cddc883be06e10ffed4be6307899fbd4`.
- Clean Greenhouse executions: `dander-greenhouse-public-8x9j9`, `-9ndj6`, and `-g77d2`; Dander runs `6363656f…`, `67f848df…`, and `8b7d1c84…`; each extracted/affected 21 rows, built one model, passed three tests, and published one asset.
- Clean evidence: ignored `evidence/clean-project-20260801`; bootstrap, cost guard, transforms/replay, and retained inventory are `passed`; authenticated HubSpot, Storage Write, WIF IAM, and Dataplex are explicitly `skipped`.
- Runtime manifest digest: `sha256:a4ec1a3eca1e4c3963ea461c9134ddc1d4d00b134fd30c2f13c4c57805962289`.
- Greenhouse: Cloud Run execution `dander-greenhouse-public-nm8wg`; Dander run `2441c4843aab418fb9d6e9523eb9b0c2`; 21 extracted, one model, three tests, one catalog asset.
- HubSpot: Cloud Run execution `dander-hubspot-companies-l2g6c`; Dander run `6e3258bc0eab4a47ad1bfeae38704912`; source access succeeded, one model, three tests, one catalog asset.
- Clean-project HubSpot recovery/replay: executions `dander-hubspot-companies-ltzhd` and `-5vvwd`; Dander runs `46f74635ca26442ab5a7ad4ea92660e7` and `53cd93774a8a42929374d51753e76b43`; each completed with one extracted/affected row, one model, three assertions, and one schema-v2 catalog asset.
- Failure delivery smoke: controlled no-op execution `dander-hubspot-companies-mnfxq` failed after its configured retry and opened incident `0.oaxg8wnfqgc7`; BigQuery counts/hash and the terminal Dander run stayed unchanged.
- Existing-sandbox deployment summaries remain under ignored `evidence/platform-greenhouse` and `evidence/platform-hubspot`.

## Release boundaries

- Dander does not create or billing-link a GCP project; `dander init` provisions the platform inside an existing project. The approved clean proof project and its inventoried resources are intentionally retained.
- The USD 5 budget guard is simulation-first and does not mathematically cap delayed cloud charges.
- Both schedules are live. HubSpot uses a dedicated disposable account, persistent synthetic seed, and read/write company scopes approved for this test; production tenants should narrow scopes to their real requirements.
- Live Storage Write, private enterprise tenants, and optional Dataplex publication are not implied by the two hosted pipeline proofs.

## Verdict

The repository, retained sandbox, and clean proof project demonstrate the promised vertical slice: one manifest and CLI provision/reconcile additive hosted pipelines, ingest and transform through one executor, persist an inspectable metadata/run spine, and alert an operator on hosted failure. Storage Write, WIF artifact-upload, and optional Dataplex proofs remain separate.
