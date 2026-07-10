# Dander

Open-source, GCP-native EL(T) suite: read from SaaS systems (Salesforce, Workday, Greenhouse,
NetSuite, Marketo, Xactly, …) and ingest efficiently + idempotently into **BigQuery**. A
self-owned replacement for Informatica and a customizable stand-in for dbt/SQLMesh.

> **Status:** governance layer only. No platform code yet — the steering files and agent workforce
> come first so everything built later inherits our standards.

## Steering — the contract (read these; they are binding)

These three are **universal** — they apply to every agent and every change, so they're loaded
into every session:

@steering/00-project-overview.md
@steering/01-security.md
@steering/02-engineering.md

**Language rules load on demand (Kiro-style conditional inclusion), not globally** — an agent
reads only the file matching what it's touching, which keeps the main thread lean:
- Python → `steering/languages/python.md`
- BigQuery SQL → `steering/languages/sql.md`
- Terraform/HCL → `steering/languages/terraform.md`

**The three rules that are never bent:** (1) no hardcoded secrets — ever, everything is env/Secret
Manager (`steering/01-security.md`); (2) interface-first, provider-abstracted design
(`steering/02-engineering.md`); (3) stay inside the scope in `steering/00-project-overview.md`.

## The agent workforce (`.claude/agents/`)

| Agent | Role |
|---|---|
| **product** | Plain-English request → small, independently-implementable tickets with acceptance criteria. |
| **design** | Ticket → clean OOP/interface-first technical design. |
| **code-python** / **code-sql** / **code-terraform** | Implement a ticket in that language against its design; typed, tested, convention-clean. |
| **pr-review** | Quality gate: implementation vs. acceptance criteria + steering → PASS, or FAIL + addendum. |
| **documentation** | READMEs, docstrings/YAML sidecars, module docs; keeps docs true to code. |

## Orchestration — the `feature` workflow

Automated, via `.claude/workflows/feature.js`. It runs the full loop:

```
request → Product (writes tickets/) → Design (per ticket) → Build[ Code → PR-Review → (FAIL → Code)… ]
```

- **Product** decomposes the request into ticket files.
- **Design** produces a technical design per ticket (concurrently).
- **Build** implements + reviews each ticket **serially**; a FAIL loops back to the code agent with
  a concrete addendum, up to a capped number of rounds, until PASS.

**Run it** (requires explicit opt-in each time — say "use a workflow" / "ultracode"):
> Run the `feature` workflow with args: `"<describe the feature in plain English>"`.

Subagents can't spawn subagents, so this loop is driven from the top by the workflow — that's why
orchestration lives in a Workflow script, not inside an agent.

## Tickets (`tickets/`)

Local markdown, one file per ticket, git-tracked. Lifecycle:
`open → in-design → in-code → in-review → done` (FAIL sends it back to `in-code`). Format spec in
`tickets/README.md`; skeleton in `tickets/TEMPLATE.md`.

## Repo map

```
CLAUDE.md                 ← you are here; loads steering + describes the workforce
steering/                 ← binding rules (overview, security, engineering, languages/)
.claude/agents/           ← the workforce definitions
.claude/workflows/        ← feature.js orchestration
tickets/                  ← work items (markdown)
.env.example              ← secret KEYS only (real .env is git-ignored)
```

## Conventions for any agent working here

- Read the relevant steering before writing code; when steering and a request conflict, surface it.
- Every code change traces to a ticket; the ticket's acceptance criteria are the definition of done.
- Record real product decisions in the Decision Log at the bottom of `steering/00-project-overview.md`.
