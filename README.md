# Dander

**An opinionated, self-hosted, GCP-native data platform you own** — ingest + transform + catalog
behind one CLI. A focused replacement for Informatica and a customizable stand-in for dbt.

> Think *"Terraform for your data platform."* `dander init` stands up the GCP infrastructure;
> `dander run` extracts your SaaS systems into BigQuery; the transform engine models the data; and
> a single metadata spine keeps your catalog and semantic layer in sync.

## Why it exists

Every existing tool does one slice: **dlt** ingests, **dbt** transforms, **Airbyte/Meltano** are
platforms but heavy or bring-your-own-everything. None ship an opinionated, self-hosted, GCP-native
system that fuses ingest + transform + catalog and that a small team fully owns — no per-row bill,
no vendor-consolidation risk. That's the gap dander fills.

### The wedge — what makes it different

1. **Batteries-included + self-provisioning.** One CLI provisions Secret Manager, IAM/WIF,
   Cloud Run, and BigQuery, then runs your pipelines.
2. **Enterprise SaaS auth as a first-class citizen.** Workday RaaS, NetSuite OAuth1 TBA, Xactly —
   the connectors that are painful everywhere else, as vetted, typed auth *strategies*.
3. **A single metadata spine.** One YAML per model/source projects to SQL **and** your data catalog
   (Dataplex aspects) **and** a semantic/agent registry. Define once, project everywhere.
4. **You own all of it.** Open source, customizable, GCP-opinionated.

## Architecture

Hybrid ingestion (dlt for standard REST APIs, hand-rolled extractors for gnarly enterprise sources —
both behind one `Source` interface) → explicit, idempotent BigQuery **write patterns** → our own
**transform engine** (`ref()` DAG → topological execution + tests) → **catalog** publication.
See `steering/00-project-overview.md` for the full module map and decision log.

## Stack

Python 3.12 (app + CLI) · BigQuery SQL (transforms) · Terraform/HCL (infra) · YAML (config).

## Repo map

```
src/dander/     core · security · ingestion · writer · transform · catalog · state · cli
infra/          Terraform modules (secret-manager, iam, compute-run, bigquery)
connectors/     per-source YAML configs
models/         SQL transform models + YAML sidecars
tests/
steering/       binding rules for humans + agents (read these)
tickets/        work items
.claude/        agent workforce + feature workflow
```

## Getting started (planned)

```bash
uv sync --extra dev          # install
uv run dander --help         # CLI
uv run pytest                # tests
```

## Status

Early scaffold. Interfaces and structure are in place; module implementations are tracked as
tickets in `tickets/` and built by the agent workforce via the `feature` workflow. **Not yet
suitable for production, and not to be open-sourced before internal OSS/legal review** (it touches
HR/comp and customer data — see `steering/00-project-overview.md`).

## License

Apache-2.0.
