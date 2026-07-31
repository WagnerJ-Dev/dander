---
id: DANDER-56
title: Verify resource-scoped runtime IAM
status: in-code
component: python
epic: proof-release
depends_on: [DANDER-54]
created: 2026-07-31
---

## Context

Project-level IAM checks do not prove the runtime's dataset, secret, Dataplex, and service-account
contract.

## Acceptance Criteria

- [x] Expected and missing dataset/secret bindings are distinguished.
- [x] Unexpected broad resource bindings fail verification.
- [x] Dataplex and service-account permissions are checked according to runtime mode.

## Design

Query each resource policy read-only and report sanitized role/resource categories.

## Implementation Notes

Implemented in `DeploymentVerifier` with read-only dataset, Secret Manager, project IAM, and
service-account policy checks plus contract tests. A real cloud result remains unclaimed.

## Review Log
