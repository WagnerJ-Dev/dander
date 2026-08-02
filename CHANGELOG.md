# Changelog

Release notes for Dander are kept here and copied into the matching GitHub Release. Dander follows
semantic versioning while it is alpha: `0.1.x` contains fixes only, and the next product capability
will be `0.2.0`.

## 0.1.0 — unreleased alpha

### Added

- Installable `dander-platform` package and source-free generated projects; imports and the CLI
  remain `dander`.
- Bounded hosted ingestion, declared schemas, concurrency fencing, cursor compare-and-set, durable
  run history, and failure alerting.
- Greenhouse and HubSpot hosted pipelines with transforms, tests, metadata, and replay-safe writes.
- Hosted Greenhouse quickstart, upgrade runbook, security policy, supported-version statement, and
  consolidated known limitations.

### Changed

- Classify the public product and package metadata as alpha.
- Correct retained-project documentation to reflect that both hosted schedules are enabled.

### Release gate

Publication waits for bounded candidate acceptance in the retained project and one independent,
source-free Greenhouse installation in a fresh disposable GCP project. The post-release operator
soak does not block this release.

## 0.1.0rc5 — 2026-08-02

### Fixed

- Report the missing immutable image for plan-only `dander init` as a normal CLI usage error
  instead of exposing a Python traceback.

## 0.1.0rc4 — 2026-08-02

### Fixed

- Wait for new-project Cloud Functions service identities and cost-guard IAM grants to propagate
  before starting the first function build.

## 0.1.0rc3 — 2026-08-02

### Fixed

- Wait for a newly granted stage-zero service-account impersonation role to become usable before
  starting platform Terraform, avoiding a first-run IAM propagation race.
- Set the Application Default Credentials quota project explicitly in the hosted quickstart.

## 0.1.0rc2 — 2026-08-02

### Fixed

- Keep read-only, full-extraction watermarks monotonic when records newer than the current source
  population have been deleted between runs.
- Render in-progress executions in `dander metadata runs` instead of rejecting the persisted
  `running` lifecycle state.

## 0.1.0rc1 — 2026-08-01

### Added

- Installable `dander-platform` wheel and source distribution; imports and the CLI remain `dander`.
- `dander new` with a paused, credential-free Greenhouse project, source-free runtime Dockerfile,
  and complete Terraform modules.
- Hosted SCD1 and sandbox-replace bounded ingestion, declared raw schemas, empty-source bootstrap,
  top-level nullable schema evolution, exclusive leases, fencing tokens, and cursor compare-and-set.
- Additive Greenhouse and HubSpot hosted pipelines with independent identities, schedules, secrets,
  transforms, tests, metadata snapshots, durable run history, and failure alerting.
- Exact-tag, environment-approved PyPI trusted publishing.

### Known limitations

This candidate is alpha and subject to the documented
[known limitations](docs/known-limitations.md). It is not represented as production-ready.
