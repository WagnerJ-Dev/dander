# Morning Handoff

## Finished

- Added enforced credential-free CI for Python, Terraform, container, and secret checks.
- Split Terraform into stage-zero administration and impersonated platform bootstrap; stage zero owns state and Artifact Registry prerequisites.
- Added sanitized evidence schemas, resource-scoped IAM/cost verification, HubSpot connector/proof, Storage Write/transform/Dataplex proof scripts, and a protected manual workflow.
- Hardened the HubSpot watermark/evidence path, ensured runtime-only secrets create their Secret Manager container, and retained cost-guard evidence separately from bootstrap checks.
- Established `harrisonoconnorhover/dander` as the admin-owned CI/evidence surface; fork PR #1 is open from `codex/dander-v0` into `main`.

## Try It

- Run `uv sync --frozen --extra dev` and the commands in `docs/ci.md`.
- Configure the `live-proof` GitHub environment, WIF variables, and HubSpot private-app secret before dispatching `.github/workflows/live-proof.yml`.
- Review the fork PR checks at https://github.com/harrisonoconnorhover/dander/pull/1; upstream PR #1 remains the contribution record.
- Follow [docs/live-proof.md](/Users/harrison/Documents/dander/docs/live-proof.md) for the protected environment and clean-project run.

## Checks

- `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src tests`: passed.
- `uv run pytest`: 463 passed.
- `pip-audit` on the exported frozen requirements: no known vulnerabilities.
- Terraform format/validate passed for `infra` and `infra/bootstrap-admin`.
- Docker build was attempted but the base-image pull stalled locally.
- `git diff --check`: passed.
- Fork PR CI passed Python, Terraform, secret, and container checks. Review the latest checks on PR #1 before merging.

## Decisions

- Keep live proofs simulation-first and retain only hashes, counts, identifiers, and statuses.
- Keep the HubSpot proof limited to synthetic companies; do not seek candidate/contact data.
- Keep the pull request draft until a real workflow artifact is reviewed.
- Keep the fork as the execution surface while preserving upstream PR #1 for review continuity; commit SHAs remain unchanged.

## Remaining

- Do not run the deployed proof job until the cost-guard function is restored to simulation mode; the read-only audit found `SIMULATE_DEACTIVATION=false`.
- Reconcile the existing sandbox with the stronger verifier (staging/marts dataset bindings are missing; the cost-guard function is currently live mode; no secret is requested by the current proof).
- Configure the GitHub environment/WIF and run the approved live proof on a clean billing-linked project. A fresh stage-zero plan for `my-project-1708716454186` is ready in `/tmp` (30 adds, 0 changes, 0 destroys; SHA-256 `3c87fac2477e5dd23b26bf0a5f79decbd9f76e5adc0e813b439e7120e03c442e`); it has not been applied.
- Re-anchor the GCP WIF repository condition and protected environment variables to `harrisonoconnorhover/dander` before dispatching the live-proof workflow.
- Create the HubSpot private app/token and store it only as the environment secret.
- Review the resulting evidence artifact and update release status from retained evidence.

## Review First

- `.github/workflows/live-proof.yml` ordering and protected-environment configuration.
- `infra/bootstrap-admin` and the data-source handoff for the Artifact Registry repository.
- `src/dander/bootstrap/verify.py` resource-scoped IAM and cost-guard checks, including actual gcloud output shapes.
