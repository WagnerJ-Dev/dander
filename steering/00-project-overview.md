# Project Overview — Dander

> **What every agent should know before touching this repo.** This is the north star.
> When a product decision is made, append it to the Decision Log at the bottom — this file is
> the single source of truth for "why is it this way."

## One-liner

Dander is an open-source, GCP-native EL(T) suite for reading from SaaS systems
(Salesforce, Workday, Greenhouse, NetSuite, Marketo, Xactly, …) and ingesting them
**efficiently and idempotently into BigQuery** — a focused, self-owned replacement for
Informatica, and a customizable stand-in for dbt/SQLMesh transformation.

## Why this exists

- **Informatica is painful** and expensive; we want to own the tooling.
- **dbt Core is free but not fully ours**, and the transformation OSS landscape consolidated
  under one vendor (Fivetran acquired Census, Tobiko/SQLMesh, and dbt Labs across 2025–2026).
  Owning the transform layer removes vendor-consolidation risk.
- We run on **GCP** and land everything in **BigQuery**. GCP-first, with clean provider
  abstractions so AWS/Azure can be added later without a rewrite.

## Modules (the target architecture — NOT yet built)

| Module | Responsibility |
|---|---|
| **Security** | GCP Secret Manager backing store; pluggable auth **strategy** per system (OAuth2 client-creds / JWT, OAuth1 TBA, API-key/basic). Token caching + refresh + **audit logging** of credential access. |
| **Generic Ingestion** | Each source is a **config object** (base URL, auth ref, endpoints, pagination, incremental cursor, field mappings). Rate limiting/backoff per source. JSON-Schema-inferred type casting to BigQuery types with per-field overrides. |
| **BigQuery Writer** | Multiple write patterns: SCD1 (MERGE), SCD2 (versioned rows), daily snapshot (partitioned append), incremental (watermark). Storage Write API vs load jobs per workload. |
| **Transform** | dbt-replacement: Jinja2 `ref()` templating → parsed dependency DAG → topological execution. Materializations reuse the Writer patterns. Generic tests (not-null/unique/accepted-values/relationships). One YAML per model feeds SQL + Dataplex catalog aspects + semantic registry. |
| **Bootstrap CLI** | pip-installable; wraps **Terraform** to provision Secret Manager, service accounts + least-privilege IAM (Workload Identity Federation), a compute target (Cloud Run jobs), and BigQuery datasets. Provider-abstracted for future AWS/Azure. |
| **Orchestration/State** | Scheduler (Cloud Scheduler + Cloud Run, or Composer) + a small control table tracking last successful cursor per source/entity for idempotent restarts. |

## Scope discipline (non-goals)

- Not a general-purpose "everything" tool. We read APIs → land in BigQuery. That's the core.
- Prove the pattern on **low-friction sources first** (Greenhouse, Marketo) end-to-end
  before tackling ugly auth/data shapes (Workday, NetSuite).
- Borrow vs. build is decided per-module in the Decision Log — don't reinvent pagination/retry
  if a library (e.g. `dlt`) earns its place; the *differentiated* layers are Security + Writer + Transform.

## Tech stack

- **Python 3.12+** — primary application language. See `languages/python.md`.
- **BigQuery Standard SQL** — transforms. See `languages/sql.md`.
- **Terraform (HCL)** — infrastructure-as-code. See `languages/terraform.md`.
- **GCP Secret Manager** — the only place real credentials live.

## Compliance note (read before open-sourcing)

This touches HR/comp data (Workday, Xactly) and customer data (Salesforce, NetSuite) at a
regulated company. **Clear internal OSS/legal review before publishing.** Treat this as a
blocking gate on any public release, separate from engineering readiness.

---

## Decision Log

Append newest at top. Format: `- YYYY-MM-DD — decision — rationale`.

- 2026-07-09 — **Orchestration = automated Workflow** (`.claude/workflows/feature.js`) — user wants hands-off fan-out of the product→design→code→review loop.
- 2026-07-09 — **Tickets = local markdown** under `tickets/` — git-trackable, no external deps.
- 2026-07-09 — **IaC = Terraform (HCL)** — mature multi-cloud providers; adding a cloud later is a new module, not a rewrite.
- 2026-07-09 — **Governance-first bootstrap** — steering files + agent workforce built before any platform code.
