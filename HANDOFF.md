# Morning Handoff

## Finished

- Extended `dander run` with an ordered transform/test and metadata tail.
- Scheduled only the public Greenhouse jobs model after guarded ingestion.
- Included models in the runtime image and granted dataset-scoped transform access.
- Kept Dataplex API, IAM, and publication behind one explicit bootstrap flag.
- Updated the upstream alignment ledger and hosted-run documentation.

## Try It

Run `uv run dander run greenhouse_job_board --guarded-free-tier --build-models
--select-model stg_greenhouse__jobs --catalog-output /tmp/dander-catalog.json`.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed across 88 source files.
- Hosted-tail and bootstrap tests — 16 passed.
- `terraform -chdir=infra fmt -recursive -check` — passed.
- `terraform -chdir=infra validate` — passed.

## Decisions

- The hosted public run selects only `stg_greenhouse__jobs`.
- Transform tests precede registry or Dataplex publication.
- Hosted Dataplex publication remains off by default because storage may be billable.

## Remaining

- Complete the requirement-by-requirement release audit.
- Obtain upstream-required OSS/legal approval before customer-data release.
- Run billable/provider integrations only with explicit authorization and credentials.

## Review First

- `src/dander/cli/main.py`
- `infra/modules/scheduled-job/main.tf`
- `tests/cli/test_hosted_tail.py`
