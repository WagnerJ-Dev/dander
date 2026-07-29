---
id: DANDER-24
title: Public Greenhouse Job Board and Harvest v3 OAuth
status: done
component: python
epic: runtime
depends_on: [DANDER-20]
created: 2026-07-29
---

## Context

The first runnable connector targeted Harvest v1 and therefore required a paid Greenhouse account
or sandbox. Greenhouse's public Job Board API can prove the live extraction path without a
credential, while Harvest v1/v2 are scheduled to become unavailable after 2026-08-31. The private
connector needs Harvest v3 OAuth client credentials without conflating it with the public path.

## Acceptance Criteria

- [x] A public connector extracts Greenhouse's published jobs without reading any secret.
- [x] Enveloped REST responses can declaratively select their record array.
- [x] The canonical private Greenhouse connector uses Harvest v3 and OAuth client credentials.
- [x] OAuth exchanges credentials using HTTP Basic, caches the bearer token, and refreshes it
      before expiry or on explicit request without logging credentials or tokens.
- [x] The legacy v1 API-key connector remains available under an explicit temporary name.
- [x] Unit tests cover public auth, response selection, OAuth request/caching/refresh/error cases,
      strategy-specific config validation, and credential-free CLI plans.
- [x] README, environment example, decision log, and handoff describe both paths and their limits.
- [x] Ruff, formatting, strict mypy, pytest, CLI smoke checks, and a read-only live public extraction
      pass.

## Design

Keep both paths behind `DltRestSource`. A small dlt authentication adapter applies Dander's
`AuthStrategy` to every prepared request, allowing `NoAuth`, Basic API key, and refreshable OAuth
to share pagination and normalization. Connector YAML contains only secret references and
non-secret token metadata. The public connector uses Greenhouse's own board as a stable runnable
example; users can replace the board token in the path.

## Review Log

### 2026-07-29 — PASS

Reviewed the implementation against the acceptance criteria and security steering. Secret values
exist only behind `SecretStoreProvider`; test credentials and tokens are generated at runtime;
public requests resolve no secret; token errors do not expose response bodies; canonical connector
metadata matches Greenhouse's v3 authentication and pagination documentation. All repository
quality gates and the credential-free live extraction pass.
