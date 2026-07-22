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
scripts/        dev tooling (e.g. the workflow monitor)
.claude/        agent workforce, feature workflow, /feature command
```

## Developer setup (macOS)

**Prerequisites**

- [Homebrew](https://brew.sh)
- **[uv](https://docs.astral.sh/uv/)** — manages the Python toolchain and dependencies (it will
  fetch Python 3.12 itself, so you don't need to install Python separately)
- **git**
- **[Claude Code](https://claude.com/claude-code)** — only if you want to run the agentic `/feature`
  workflow (see below). Not needed to build or test the Python package.

**Install**

```bash
brew install uv                 # one-time: install uv
git clone <repo-url> dander && cd dander
uv sync --extra dev             # install app + dev deps into .venv (fetches Python 3.12 if needed)
```

That's it — `uv sync` creates the virtualenv, installs everything from `pyproject.toml`, and pins
it in `uv.lock`.

## Everyday commands

All commands run through `uv run` (no need to activate the venv manually):

```bash
uv run ruff check .        # lint
uv run ruff format .       # auto-format
uv run mypy                # strict type-check
uv run pytest              # run the test suite
uv run dander --help       # the CLI (init / run — stubs for now)
```

**Green baseline** = `ruff check`, `ruff format --check`, `mypy`, and `pytest` all pass. Keep it
green; the `pr-review` agent enforces it on every ticket.

## The agent workforce & the `/feature` workflow

Features are built by a workforce of agents defined in `.claude/` — the `feature` workflow runs the
loop **Product → Design → Code → PR-Review**, looping a ticket back to Code with an addendum until
it passes review. See `CLAUDE.md` for the full picture.

**First, register it.** `.claude/agents/`, `.claude/workflows/`, and `.claude/commands/` are loaded
only at **Claude Code startup**. After cloning (or after editing anything under `.claude/`),
**restart Claude Code in the project root** so `/feature`, the agents, and the `feature` workflow
become available.

**Then run it** (any of these — it costs tokens, so each run is an explicit opt-in):

```text
/feature Add an ApiKeyBasic auth strategy and wire GcpSecretStore
```
```text
(or just ask Claude in chat)   run the feature workflow with: <describe the feature>
```
```bash
# headless / scripted, from a terminal:
claude -p --permission-mode acceptEdits "run the feature workflow with args: <describe the feature>"
```

It writes tickets to `tickets/` (lifecycle `open → in-design → in-code → in-review → done`),
implements + reviews each until PASS, and leaves the code + tests in your working tree.

## Watching workflows in real time

A workflow run spawns many background agents. `scripts/watch_workflows.py` is a dependency-free
(stdlib-only) live dashboard — run it in a **separate terminal** while a workflow is going:

```bash
python3 scripts/watch_workflows.py          # live dashboard, refresh every 2s
python3 scripts/watch_workflows.py --all    # include finished / idle runs
python3 scripts/watch_workflows.py -n 5     # refresh every 5s
python3 scripts/watch_workflows.py --once   # print one snapshot and exit
```

It auto-discovers **all** runs across sessions (so it handles several concurrent workflows), and
shows each run's agents with their role, ticket, and live PASS/FAIL verdicts:

```text
● wf_020b226b-07f  RUNNING  elapsed 13m48s  agents 7 done
   ✓ product       —         2 ticket(s)
   ✓ design        DANDER-2  design ready
   ✓ code-python   DANDER-2
   ✓ pr-review     DANDER-2  PASS
   ▸ pr-review     DANDER-3  working…
```

## Status

Early scaffold. Interfaces and structure are in place; module implementations are tracked as
tickets in `tickets/` and built by the agent workforce via the `feature` workflow. **Not yet
suitable for production, and not to be open-sourced before internal OSS/legal review** (it touches
HR/comp and customer data — see `steering/00-project-overview.md`).

## License

Apache-2.0.
