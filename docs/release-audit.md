# Dander v0 Release Audit

Audited against the live `WagnerJ-Dev/dander` north star on 2026-07-29 and operationally refreshed
on 2026-07-30. As of 2026-07-31, the admin-owned `harrisonoconnorhover/dander` fork is the CI and
evidence execution surface; upstream PR #1 remains the contribution record. “Implemented locally”
means code, offline tests, and static infrastructure validation exist. It does not imply that
provider credentials or every billable cloud mutation have been validated. Sensitive-system names
are treated as hypothetical connector scope, not evidence of an existing-company relationship.

## Requirement evidence

| Upstream requirement | Status | Evidence |
|---|---|---|
| Secret Manager backing store and audited credential access | Implemented locally | `security/secret_manager.py`; environment-to-managed-resource routing; value-free access events; secret-resolution tests |
| API/basic, OAuth2 client credentials/JWT, and OAuth1 TBA | Implemented locally | `security/`; cached/refreshable bearer tokens; Greenhouse, Marketo, Salesforce, Workday, and NetSuite templates/tests |
| Config-driven standard REST ingestion on dlt | Implemented locally | `ingestion/dlt_backed.py`; five pagination strategies; live public Greenhouse, Lever, and Ashby connectors plus Marketo template |
| Hand-rolled enterprise ingestion behind `Source` | Implemented locally | `WorkdayRaasSource`; injected transport; paging, cursor, envelope, casting, and retry tests |
| Per-source rate limiting and bounded backoff | Implemented locally | dlt token-bucket session plus safe-read retries; Workday bounded retry path; metadata-only retry events |
| Inferred types plus per-field BigQuery overrides | Implemented locally | dlt inference on standard REST; declared scalar casts for enterprise sources; additive declared target schemas |
| SCD1, SCD2, snapshots, and incremental writes | Implemented locally | `writer/bigquery.py`; unique staging, deduplication, transactional history, cursor validation, and rerun tests |
| Storage Write API versus load jobs by workload | Implemented locally | explicit transport config; bounded load jobs; offset-checked pending streams committed atomically before keyed merge |
| `ref()` DAG and topological transform execution | Implemented locally | restricted Jinja compilation, sqlglot validation, cycle/unknown-ref rejection, and ordered BigQuery builds |
| Materializations and four generic test types | Implemented locally | view/table/incremental SQL; not-null, unique, accepted-values, and relationship assertions |
| One model YAML feeds transform, catalog, and semantics | Implemented locally | typed sidecars compile executable tests, deterministic semantic JSON, and non-deleting Dataplex aspect requests |
| Terraform bootstrap for datasets, secrets, IAM/WIF, and Cloud Run | Implemented locally | stage-zero HCL creates GCS state and Artifact Registry preconditions; main HCL requires bootstrap impersonation; immutable images; repository/ref-scoped GitHub OIDC; secret values excluded from state; read-only deployment verifier |
| Scheduled execution and restart state | Implemented locally | paused-first Scheduler → Cloud Run job; guarded ingestion → selected transforms/tests → registry; BigQuery/SQLite cursors and run summaries | Clean-project hosted run is not retained in this branch |
| CI enforcement and release gating | Implemented locally | pinned-action CI workflow, local gate documentation, protected manual proof workflow, and sanitized evidence finalizer; no GitHub check run or branch-protection configuration is currently present on the draft PR |
| Live deployment verification | Partially live-proven | read-only audit reached the billing-linked sandbox and verified project, datasets, remote state, immutable job image, scheduler, project/billing-account runtime IAM, raw dataset binding, budget, topic, and billing linkage; staging/marts bindings fail, the cost-guard function is `SIMULATE_DEACTIVATION=false`, and no proof job was executed |
| Authenticated SaaS, Storage Write, and Dataplex proofs | Implemented locally | controlled scripts and model/connector implementations exist with offline tests; no HubSpot token, live Storage Write commit, or Dataplex mutation/read-back artifact has been retained |

Transform materializations use the same idempotent BigQuery contracts as the record writers, but
query-based transforms compile SQL directly instead of passing materialized rows through the
Python `WritePattern` interface. This avoids pulling transform data out of BigQuery.

## Release boundaries

- Credential-free Greenhouse, Lever, and Ashby paths prove live public source shapes without a
  customer account. Marketo and enterprise provider exchanges are tested offline and require
  tenant access.
- The sandbox project has billing enabled, a USD 5 monthly budget, Pub/Sub notifications, and a
  billing-detachment function currently configured with `SIMULATE_DEACTIVATION=false`. No proof
  execution should proceed until that safety setting is restored and independently verified.
- Endpoint extraction is still accumulated in memory before a logical write. Bounded writer
  requests protect BigQuery payload size, not total-process memory for very large sources.
- Nested/repeated automatic schema evolution is intentionally unsupported; only declared nullable
  scalar additions are automatic.
- The architecture's HR/customer system names are product examples only. Normal provenance,
  licensing, and privacy review becomes a release gate only if employer-owned material,
  credentials, or non-public records are introduced.

## Verdict

This branch is a reasonable, runnable v0 of the stated architecture with local implementation
evidence and a partial live infrastructure audit. It is not yet a production-certified release or
the completed evidence-focused round.
The remaining production proofs need vendor credentials or deliberately scoped cloud execution;
they are not gaps that should be papered over with mocks.

See [`session-resume.md`](session-resume.md) for the current Git and deployed-sandbox snapshot.
