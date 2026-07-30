# Morning Handoff

## Finished

- Matched every named upstream module with local implementation evidence and a release audit.
- Pushed the audited v0 through `ccf0419`; later documentation clarification remains local.
- Recorded that sensitive-system names are hypothetical connector scope, not company provenance.
- Verified billing, the USD 5 guard, live billing detachment, and two hosted ingestion successes.
- Added `docs/session-resume.md` with exact Git, validation, cloud, safety, and next-step context.

## Try It

Start with `git status -sb`, then read `docs/session-resume.md`. Use `uv run dander --help` for the
local CLI; do not apply or deploy until the scheduler and per-run cost scope are explicit.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed across 88 source files.
- `uv run pytest` — 431 passed.
- Terraform formatting and validation — passed.
- Wheel install/CLI and local amd64 Docker image artifact checks — passed.
- All 76 local Markdown links resolve; secret scans found only intentional detector fixtures.

## Decisions

- Sensitive-system names are hypothetical connector scope, not company provenance.
- Synthetic data can prove Dander-controlled behavior; real tenants prove vendor behavior only.
- The USD 5 budget authorizes a bounded sandbox, not automatic permission for every cloud mutation.

## Remaining

- Decide whether to leave the daily 09:00 Cloud Scheduler run enabled.
- Run Marketo and enterprise tenant integrations when credentials are available.
- Run hosted, Dataplex, and Storage Write proofs only with explicit per-run cost approval.
- Stream/spool very large endpoint extracts instead of holding a logical batch in memory.
- Add nested/repeated schema evolution only from explicit reviewed contracts.

## Review First

- `docs/session-resume.md`
- `docs/release-audit.md`
- `docs/spec-alignment.md`
