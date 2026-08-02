# Morning Handoff

## Finished

- Renamed the distribution to `dander-platform` at `0.1.0rc1`; imports and CLI remain `dander`.
- Added `dander new DIR` with a paused Greenhouse project, Docker context, and Terraform modules.
- Built clean wheel/sdist archives that exclude Terraform state, plans, caches, and private tfvars.
- Added isolated artifact-install CI plus exact-tag, environment-gated PyPI trusted publishing.
- Made installed-project runtime image hashing work without a cloned source tree.

## Try It

- Run `uv run dander --version`.
- Run `uv run dander new /tmp/my-dander && cd /tmp/my-dander && dander validate`.
- Run `uv build` and `uv run python scripts/check_distribution.py dist/*.whl dist/*.tar.gz`.

## Checks

- Ruff lint/format, strict mypy, and all 581 tests pass locally.
- Direct wheel and sdist builds pass archive identity, required-asset, and hygiene validation.
- Both artifacts install outside the checkout; version, scaffold, project, and Terraform validate.
- Root/stage-zero Terraform, dependency audit, tracked dry-runs, and container smoke pass.

## Decisions

- Distribution name and public import/command names intentionally differ.
- Starter projects are complete but paused, guarded, and credential-free by default.
- PyPI publishing is tag-exact, trusted, and separately environment-approved.

## Remaining

- Run the full validation matrix and merge Phase 5 through protected main.
- Obtain explicit approval before creating/pushing the candidate tag or publishing to PyPI.
- No package publication, Terraform apply, or GCP mutation occurred.

## Review First

- `src/dander/project/scaffold.py`
- `pyproject.toml`
- `.github/workflows/publish.yml`
