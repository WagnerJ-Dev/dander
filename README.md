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
uv run dander --help       # the CLI (init / run)
```

**Green baseline** = `ruff check`, `ruff format --check`, `mypy`, and `pytest` all pass. Keep it
green; the `pr-review` agent enforces it on every ticket.

## Runnable v0

The first vertical slice runs the low-friction Greenhouse Harvest connector through dlt, stages
and SCD1-merges each endpoint into BigQuery, then commits its response watermark only after the
write succeeds.

Validate the connector and inspect its credential-free plan:

```bash
uv run dander run greenhouse --dry-run --project my-gcp-project
```

For local development, set `SECRET_GREENHOUSE` in `.env` to the API key. In cloud execution, set
it to the full Secret Manager resource name; Dander resolves and audits the managed-secret access.
Then execute:

```bash
uv run dander run greenhouse --project my-gcp-project
```

### Strict $0 BigQuery Sandbox

For evaluation without a billing account, create a
[BigQuery Sandbox project](https://docs.cloud.google.com/bigquery/docs/sandbox), authenticate
Application Default Credentials, and keep the Greenhouse API key local:

```bash
gcloud auth application-default login
export SECRET_GREENHOUSE='your-sandbox-greenhouse-api-key'
uv run dander run greenhouse --sandbox --project my-no-billing-project
```

`--sandbox` fails closed unless the Cloud Billing API explicitly reports that billing is disabled.
It creates the raw dataset without Terraform, resolves secrets from the environment only, replaces
each destination through a `WRITE_TRUNCATE` load job, and stores observed cursors in
`.dander/state.db`. Every sandbox run is a full refresh because BigQuery Sandbox does not support
DML, including `MERGE`. It does not use Secret Manager, GCS, Cloud Run, or other services whose
free tiers require a billing account. If Cloud Billing returns an authorization/API error, Dander
does nothing; enable API access or fix the caller's read permission, then retry.

You still need access to a Greenhouse test account/API key for a live extraction. The dry run,
local tests, and all fake-provider tests need no external credentials:

```bash
uv run dander run greenhouse --sandbox --dry-run --project my-no-billing-project
```

### Billing-linked guarded free tier

To exercise the real Secret Manager, BigQuery `MERGE`, and BigQuery watermark path, link a billing
account and configure a project-scoped budget. Google currently provides monthly free usage for
[the first 10 GiB of BigQuery storage and 1 TiB of analysis](https://cloud.google.com/bigquery/pricing),
[six active Secret Manager versions and 10,000 accesses](https://cloud.google.com/secret-manager/pricing),
and bounded [Cloud Run compute and request usage](https://cloud.google.com/run/pricing). These are
usage allowances, not a promise that the project cannot incur charges.

Create the project-scoped budget (the project filter is important):

```bash
gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT_ID" \
  --display-name="dander-sbx-cap" \
  --budget-amount=5.00USD \
  --filter-projects="projects/$PROJECT_ID" \
  --threshold-rule=percent=0.8,basis=current-spend \
  --threshold-rule=percent=1.0,basis=current-spend \
  --notifications-rule-pubsub-topic="projects/$PROJECT_ID/topics/dander-stop-billing"
```

Follow Google's
[programmatic notification setup](https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications)
and [billing-disable tutorial](https://docs.cloud.google.com/billing/docs/how-to/disable-billing-with-notifications)
to deploy `infra/functions/stop_billing` using the topic `dander-stop-billing`. Always deploy it
with `SIMULATE_DEACTIVATION=true`, publish a synthetic over-budget event, and inspect the simulation
log before switching it to `false`. Provider-managed trigger subscription names are supported.
Then run:

```bash
export SECRET_GREENHOUSE='projects/PROJECT/secrets/greenhouse/versions/latest'
uv run dander run greenhouse --guarded-free-tier --project "$PROJECT_ID"
```

Before reading the secret or extracting data, Dander requires billing enabled, the named
project-scoped USD budget at or below $5, 80% and 100% current-spend thresholds, the expected
Pub/Sub topic, and at least one attached subscription. This verifies configuration metadata; it
cannot prove the subscriber's code or runtime health. Google says budgets do not cap spending,
notifications are emitted several times daily, and charges can arrive after billing is detached.
The kill switch can stop services and make resources unrecoverable. Set the budget below the
actual amount you could tolerate and use a dedicated disposable project.

New users may instead use the [$300/90-day Free Trial](https://docs.cloud.google.com/free/docs/free-cloud-features).
While the account remains a Free Trial account, Google says usage is not charged to the payment
method; manually upgrading makes overages beyond remaining credit and free allowances billable.

The bootstrap command uses remote GCS Terraform state and plans by default. Applying requires both
the `--apply` flag and an interactive confirmation:

```bash
uv run dander init --project my-gcp-project --state-bucket my-existing-tfstate-bucket
uv run dander init --project my-gcp-project --state-bucket my-existing-tfstate-bucket --apply
```

Current v0 limits are explicit: Greenhouse/API-key-basic auth only, production SCD1 plus sandbox
full-replacement writes, whole-endpoint batches held in memory, no automatic target-schema
evolution, and bootstrap coverage for BigQuery datasets only. The guarded mode verifies budget
wiring but does not provision or continuously monitor it. Transform execution, catalog
publication, additional production write modes, IAM/WIF, Secret Manager provisioning, and Cloud
Run jobs remain future slices.

## The agent workforce & the `/feature` workflow

Features are built by a workforce of agents defined in `.claude/` — the `feature` workflow runs the
loop **Product → Design → Code → PR-Review**, looping a ticket back to Code with an addendum until
it passes review. See `CLAUDE.md` for the full picture.

**First, register it.** `.claude/agents/`, `.claude/workflows/`, and `.claude/commands/` are loaded
only at **Claude Code startup**. After cloning (or after editing anything under `.claude/`),
**restart Claude Code in the project root** so `/feature`, the agents, and the `feature` workflow
become available.
**Run "/config workflows=true" in a Claude chat window to enable it for that session.**

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

Runnable ingestion v0: the Greenhouse → BigQuery production SCD1 path, strict no-billing sandbox,
and billing-linked guarded preflight, plus audited secret resolution, watermark state, dry-run
planning, and BigQuery Terraform bootstrap are implemented and unit-tested. The limits above still
make this **unsuitable for production**, and it must not be open-sourced before internal OSS/legal
review (it touches HR/comp and customer data — see
`steering/00-project-overview.md`).

## License

Apache-2.0.
