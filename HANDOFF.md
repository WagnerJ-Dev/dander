# Morning Handoff

## Finished

- Added enforced credential-free CI for Python, Terraform, container, and secret checks.
- Split Terraform into stage-zero administration and impersonated platform bootstrap; stage zero owns state and Artifact Registry prerequisites.
- Added sanitized evidence schemas, resource-scoped IAM/cost verification, HubSpot connector/proof, Storage Write/transform/Dataplex proof scripts, and a protected manual workflow.
- Hardened the HubSpot watermark/evidence path, ensured runtime-only secrets create their Secret Manager container, and retained cost-guard evidence separately from bootstrap checks.

## Try It

- Run `uv sync --frozen --extra dev` and the commands in `docs/ci.md`.
- Configure the `live-proof` GitHub environment, WIF variables, and HubSpot private-app secret before dispatching `.github/workflows/live-proof.yml`.
- Follow [docs/live-proof.md](/Users/harrison/Documents/dander/docs/live-proof.md) for the protected environment and clean-project run.

## Checks

- `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src tests`: passed.
- `uv run pytest`: 463 passed.
- `pip-audit` on the exported frozen requirements: no known vulnerabilities.
- Terraform format/validate passed for `infra` and `infra/bootstrap-admin`.
- Docker build was attempted but the base-image pull stalled locally.

## Decisions

- Keep live proofs simulation-first and retain only hashes, counts, identifiers, and statuses.
- Keep the HubSpot proof limited to synthetic companies; do not seek candidate/contact data.
- Keep the pull request draft until a real workflow artifact is reviewed.

## Remaining

- Do not run the deployed proof job until the cost-guard function is restored to simulation mode; the read-only audit found `SIMULATE_DEACTIVATION=false`.
- Reconcile the existing sandbox with the stronger verifier (staging/marts dataset bindings are missing; the cost-guard function is currently live mode; no secret is requested by the current proof).
- Configure the GitHub environment/WIF and run the approved live proof on a clean billing-linked project.
- Create the HubSpot private app/token and store it only as the environment secret.
- Review the resulting evidence artifact and update release status from retained evidence.

## Review First

- `.github/workflows/live-proof.yml` ordering and protected-environment configuration.
- `infra/bootstrap-admin` and the data-source handoff for the Artifact Registry repository.
- `src/dander/bootstrap/verify.py` resource-scoped IAM and cost-guard checks, including actual gcloud output shapes.
