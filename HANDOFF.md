# Morning Handoff

## Finished

- Added opt-in Secret Manager containers with per-secret runtime IAM and no managed values.
- Added repository/ref-scoped GitHub OIDC WIF with no service-account keys.
- Scoped image push access to Dander's Artifact Registry repository and `actAs` to its runtime identities.
- Extended `dander init` to safely plan the complete optional runtime from literal arguments.
- Documented security decisions and refreshed the upstream alignment ledger.

## Try It

```bash
uv run dander init --help
uv run dander init --project PROJECT --state-bucket BUCKET
```

Add `--enable-runtime`, billing account, immutable image digest, secret ids, and GitHub repository
only when intentionally planning the hosted slice. It remains plan-only unless `--apply` is used
and confirmed.

## Checks

- `uv run ruff check .` and `uv run ruff format --check .` — passed.
- `uv run mypy src tests` — passed in strict mode.
- `uv run pytest` — 358 passed.
- `terraform fmt -recursive -check` and `terraform validate` — passed.
- Live disabled-feature plan: no changes; opt-in feature plan: 14 adds, 0 changes, 0 destroys.

## Decisions

- Terraform never handles secret values or creates secret versions.
- GitHub deployment uses narrowly scoped OIDC rather than a downloaded key.
- Runtime images must use immutable SHA-256 digests; apply uses the reviewed saved plan.

## Remaining

- Integrate cost-guard infrastructure into `dander init`.
- Implement incremental, SCD2, and snapshot materializations.
- Execute visual mapping/join/custom-code pipeline definitions.
- Prove a concrete hand-rolled enterprise connector.
- Complete the release audit and external legal gate.

## Review First

- `infra/modules/github-wif/main.tf`
- `infra/modules/secret-manager/main.tf`
- `src/dander/bootstrap/terraform.py`
