# Morning Handoff

## Finished

- Defined three Workday-facing operations: tenant token issuance plus workers and organizations
  RaaS reports; three separate operations control only the simulator.
- Added a stateful FastAPI service with invented paged fixtures, cursor-driven updates, and named
  expired-credential, throttling, missing-permission, and malformed-record scenarios.
- Ran Dander's real OAuth strategy and `WorkdayRaasSource` against the loopback service.
- Made Workday 401/403 responses fail immediately with sanitized messages while retaining bounded
  retries for 429, server, and transport failures.
- Aligned the example connector and documented the later real-tenant acceptance boundary.

## Try It

```bash
uv sync --extra dev
uv run python -m dander.dev.workday_simulator
uv run pytest tests/integration/test_workday_simulator.py
```

## Checks

- Focused Workday tests: 16 passed.
- Full suite: 604 passed; Ruff lint/format and strict mypy passed.
- Locked dependency audit: no known vulnerabilities.
- Terraform formatting and both backend-disabled validations passed.
- Wheel/sdist inspection and packaged fixtures passed; the container built, started the CLI as
  non-root user `65532`, and retained the hosted HubSpot proof assets.

## Decisions

- RaaS is the bounded read-only acceptance surface; SOAP remains out of scope.
- Simulator controls are explicitly not Workday API operations.
- Tenant-specific OAuth grant, prompts, and domain permissions remain live acceptance questions.

## Remaining

- Later, use one disposable/sandbox tenant for the documented narrow Workday acceptance.

## Review First

- `contracts/workday-raas-simulator.openapi.yaml`
- `src/dander/dev/workday_simulator.py`
- `tests/integration/test_workday_simulator.py`
