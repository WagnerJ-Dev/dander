---
id: DANDER-54
title: Require Terraform bootstrap impersonation
status: in-code
component: terraform
epic: proof-release
depends_on: [DANDER-53]
created: 2026-07-31
---

## Context

The platform apply must run as `dander-bootstrap`, not as the administrator who created it.

## Acceptance Criteria

- [x] Main provider supports explicit service-account impersonation.
- [x] Platform plan/apply fails when impersonation is absent and succeeds when configured in tests.
- [x] Evidence can identify the configured impersonated service-account email without tokens.

## Design

The CLI passes a validated service-account email to Terraform and sets the provider's impersonation
boundary for every platform command.

## Implementation Notes

Implemented in `infra/versions.tf`, `TerraformBootstrap`, the explicit platform CLI commands, and
the workflow identity proof at `scripts/live_proof/identity.py`. The proof retains only caller
type and bootstrap service-account identity, not the active caller email or token.

## Review Log
