# DANDER-23 — Deployable billing kill switch

Status: done

## Context

Guarded mode verifies budget wiring but previously supplied no handler. The live disposable project
needs a small, testable Cloud Run function based on Google's documented billing-disable pattern.

## Acceptance criteria

- The function ignores malformed events and notifications for other budgets.
- The function takes action only when current cost is at or above the budget amount.
- Simulation mode performs no billing mutation.
- Live mode checks current billing state and idempotently unlinks the project.
- The project id and expected budget name come from environment configuration.
- Unit tests use a fake billing client.
- Guarded preflight accepts a real provider-managed subscription attached to the expected topic.
- Deployment is simulation-tested before live mode is enabled.

## Review

PASS — malformed, non-finite, unrelated, and under-budget events cannot mutate billing. Unit tests
prove threshold, simulation, live, and idempotent behavior. The live deployment was tested in
simulation before enabling detachment; its trigger retries and its private service grants invocation
only to the dedicated identity. Ruff, formatting, strict mypy, and all 312 tests pass. Dander's live
guarded preflight passes and billing remains enabled.
