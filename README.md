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

## Runnable Greenhouse paths

The free first path reads published jobs from Greenhouse's public Job Board API. It uses
Greenhouse's own board as a live example, needs no Greenhouse account or credential, and exercises
the same dlt → BigQuery writer path as private connectors:

```bash
uv run dander run greenhouse_job_board --dry-run --project my-gcp-project
uv run dander run greenhouse_job_board --guarded-free-tier --project my-gcp-project
```

To read another organization's published jobs, copy the connector and replace `greenhouse` in
`/greenhouse/jobs` with the public board token from its job-board URL. Public GET requests return
published job data only; they do not expose candidates, applications, or other private records.

The canonical `greenhouse` connector reads private candidates and jobs through Harvest v3. It
uses OAuth 2.0 client credentials, caches expiring access tokens, and applies the token to every
paginated request. Export the two credential references locally, or point each environment value
at a full Secret Manager version resource in cloud execution:

```bash
read -r SECRET_GREENHOUSE_CLIENT_ID
read -rs SECRET_GREENHOUSE_CLIENT_SECRET && printf '\n'
export SECRET_GREENHOUSE_CLIENT_ID SECRET_GREENHOUSE_CLIENT_SECRET
uv run dander run greenhouse --project my-gcp-project
```

Create Harvest v3 credentials in Greenhouse under **Configure → Dev Center → API Credential
Management**, choose **Harvest V3 (OAuth)**, and grant only the read scopes for candidates and
jobs. By default Greenhouse attributes requests to the integration service user associated with
the credential. An optional integer `auth_options.subject` can select a different Greenhouse user.
See Greenhouse's [v3 authentication guide](https://harvestdocs.greenhouse.io/docs/authentication).

`greenhouse_harvest_v1_legacy` preserves API-key compatibility during migration only. Greenhouse
states that Harvest v1/v2 become unavailable after 2026-08-31; new deployments should not use it.

`connectors/marketo.example.yaml` is the second standard-REST template. Copy it to
`connectors/marketo.yaml`, replace `MUNCHKIN_ID`, and provide the two named secret references.
It follows Adobe's current two-legged OAuth token shape, sends API access tokens in the
`Authorization` header, pages the read-only Programs endpoint, and enforces the documented
[five-request-per-second instance rate](https://experienceleague.adobe.com/en/docs/marketo-developer/marketo/rest/rest-api).
See Adobe's [authentication guide](https://experienceleague.adobe.com/en/docs/marketo-developer/marketo/rest/authentication)
for the tenant-side custom-service setup.

### Hand-rolled Workday path

`WorkdayRaasSource` proves the second half of the hybrid-ingestion design without dlt. Copy
`connectors/workday_raas.example.yaml`, supply your tenant/report identifiers and secret
references, then run it through the same CLI/runtime/writer path. The source owns page-number
pagination, cursor parameters, bounded backoff, response-envelope validation, and declared
BigQuery scalar casts. Its complete test suite uses an injected fake transport; no Workday
credential or employee row is stored in this repository.

### Enterprise authentication templates

`connectors/salesforce_jwt.example.yaml` demonstrates OAuth2 JWT bearer authentication with an
RSA-key reference, optional delegated subject, and a conservative token cache for providers that
omit `expires_in`. `connectors/netsuite.example.yaml` demonstrates OAuth1 TBA with four credential
references and HMAC-SHA256 request signing. Copy either template to a local connector and replace
only account/endpoint identifiers and secret reference names; do not place credential values in
YAML.

### Strict $0 BigQuery Sandbox

For evaluation without a billing account, create a
[BigQuery Sandbox project](https://docs.cloud.google.com/bigquery/docs/sandbox), authenticate
Application Default Credentials, then run the public connector:

```bash
gcloud auth application-default login
uv run dander run greenhouse_job_board --sandbox --project my-no-billing-project
```

`--sandbox` fails closed unless the Cloud Billing API explicitly reports that billing is disabled.
It creates the raw dataset without Terraform, resolves secrets from the environment only, replaces
each destination through a `WRITE_TRUNCATE` load job, and stores observed cursors in
`.dander/state.db`. Every sandbox run is a full refresh because BigQuery Sandbox does not support
DML, including `MERGE`. It does not use Secret Manager, GCS, Cloud Run, or other services whose
free tiers require a billing account. If Cloud Billing returns an authorization/API error, Dander
does nothing; enable API access or fix the caller's read permission, then retry.

The public connector, dry runs, local tests, and all fake-provider tests need no external
credentials. Harvest v3 still requires access to a Greenhouse customer account:

```bash
uv run dander run greenhouse_job_board --sandbox --dry-run --project my-no-billing-project
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
export SECRET_GREENHOUSE_CLIENT_ID='projects/PROJECT/secrets/greenhouse-client-id/versions/latest'
export SECRET_GREENHOUSE_CLIENT_SECRET='projects/PROJECT/secrets/greenhouse-client-secret/versions/latest'
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

Optional flags can include the complete hosted slice in the same reviewed plan:

```bash
uv run dander init \
  --project my-gcp-project \
  --state-bucket my-existing-tfstate-bucket \
  --enable-runtime \
  --billing-account ABCDEF-123456-ABCDEF \
  --container-image us-central1-docker.pkg.dev/my-gcp-project/dander/dander@sha256:DIGEST \
  --secret-id greenhouse-client-secret \
  --github-repository owner/repository \
  --enable-cost-guard
```

The image must use an immutable SHA-256 digest. Secret Manager containers and narrowly scoped
runtime access can be managed by Terraform, but secret values never enter Terraform state.
GitHub Actions authenticates through repository/ref-constrained OIDC rather than a downloaded key.
Add `--runtime-publish-dataplex` only when you explicitly want hosted runs to store catalog
aspects; it enables the API and IAM required for that potentially billable operation.
The integrated cost guard creates the project budget, Pub/Sub wiring, and Gen 2 function in
simulation mode. Live billing detachment requires the additional `--live-cost-guard` flag and is
called out in the apply confirmation. Function deployment uses billable Cloud Build, Cloud Run,
Storage, and Artifact Registry services; free allowances do not make this a hard $0 guarantee.

### Scheduled public pipeline

The hosted slice runs the credential-free Greenhouse Job Board connector as a Cloud Run Job, builds
and tests `stg_greenhouse__jobs`, then compiles its semantic registry. Terraform creates separate
runtime and scheduler service accounts, grants the runtime write access only to `raw`, `staging`,
and `marts`, and invokes the job daily at 09:00 in `America/New_York`. Dataplex publication remains
off unless explicitly enabled. The schedule defaults to paused so a complete manual execution can
be verified before enabling it.

Build for Cloud Run, push the image, and use its immutable digest in a local tfvars file:

```bash
PROJECT_ID=my-gcp-project
REGION=us-central1
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/dander/dander"

docker build --platform linux/amd64 -t "$IMAGE:dander-25" .
gcloud auth configure-docker "$REGION-docker.pkg.dev"
docker push "$IMAGE:dander-25"
docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE:dander-25"

cp infra/sandbox.auto.tfvars.example infra/sandbox.auto.tfvars
# Fill in the billing account and image digest; keep scheduler_paused = true.
terraform -chdir=infra plan -out=scheduled.tfplan
terraform -chdir=infra apply scheduled.tfplan
gcloud run jobs execute dander-greenhouse-public --region="$REGION" --wait
```

After the manual ingestion, transform tests, and local registry compilation succeed, set
`scheduler_paused = false`, review a fresh saved plan, and apply that exact plan. The image
repository deletes untagged images after one day and retains the three most recent versions. A
single Scheduler job is within Google's current three-job monthly free allowance, and small Cloud
Run executions may fit its free compute allowance, but neither is a hard spending cap. The guarded
CLI preflight and budget kill switch remain required.

### Build and test SQL models

Every SQL model has a YAML sidecar that defines its materialization, catalog metadata, columns, and
generic tests. Dander validates the complete project, resolves `ref()` dependencies, orders models,
compiles one read-only BigQuery query per model, materializes views or tables, and then runs the
declared assertions:

```bash
uv run dander build \
  --project "$PROJECT_ID" \
  --select stg_greenhouse__jobs \
  --guarded-free-tier

uv run dander test \
  --project "$PROJECT_ID" \
  --select stg_greenhouse__jobs \
  --guarded-free-tier
```

Repeat `--select` to build multiple roots; their model dependencies are included automatically.
Omit it to build every model. References beginning with `raw_` resolve by convention to
`raw.<remaining_name>`; other references must name a discovered model. Unknown references, cycles,
missing/invalid sidecars, non-query SQL, and unsupported incremental materializations fail before
the first BigQuery query. Generic tests currently support not-null, unique, accepted-values, and
relationships.

### Compile the metadata spine

The same model sidecar also projects into a deterministic semantic registry and Dataplex Knowledge
Catalog aspects:

```bash
uv run dander catalog \
  --project "$PROJECT_ID" \
  --select stg_greenhouse__jobs \
  --output .dander/catalog.json
```

Local compilation is the default. `--publish-dataplex` explicitly attaches overview, contacts,
schema, and generic system aspects to the corresponding BigQuery entry; it can be combined with
`--guarded-free-tier`. Publication never deletes unrelated aspects. Google currently makes
Knowledge Catalog API calls free but charges for stored aspect metadata, so cloud mutation is not
implicit. See [Knowledge Catalog pricing](https://cloud.google.com/products/knowledge-catalog/pricing)
and [Dataplex aspect management](https://docs.cloud.google.com/dataplex/docs/enrich-entries-metadata).

Current v0 limits are explicit: the writer package executes SCD1, cursor-validated incremental,
partitioned snapshot, SCD2 history, and sandbox replacement, but whole endpoint batches are held in
memory. Schema evolution is intentionally limited to declared nullable scalar additions, and the
Storage Write transport supports an explicitly bounded scalar subset. Public Job Board extraction
is a full refresh and does not delete jobs that disappear from a board. The CLI bootstrap can plan
Secret Manager, IAM/WIF, the complete scheduled public pipeline, and a simulation-first cost guard,
but deploying those opt-in services may be billable. Visual graph execution supports safe mappings,
expressions, built-in transforms, and two-input joins; live provider/catalog/Storage Write proof
still requires external accounts or billable services. The tracked completion ledger is in
[`docs/spec-alignment.md`](docs/spec-alignment.md).

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
make this **unsuitable for production**. The named HR, compensation, and customer systems describe
possible connector categories; they do not imply that this repository came from, connects to, or
contains data from an existing company. Normal provenance, licensing, and privacy review still
applies before adding employer-owned code or non-public data.

For the exact current branch, validation, deployed-sandbox, and next-session state, see
[`docs/session-resume.md`](docs/session-resume.md).

## License

Apache-2.0.
