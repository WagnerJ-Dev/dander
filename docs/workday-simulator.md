# Workday RaaS simulator

Dander's first Workday acceptance is deliberately read-only and small. It uses custom
Reports-as-a-Service (RaaS) rather than pretending to model the complete Workday API or SOAP
surface. Workday documents RaaS as the mechanism for exposing a tenant-defined custom report in
JSON or XML, and recommends bounded backoff when tenant load produces HTTP 429 or 500 responses.

The tracked contract is [`contracts/workday-raas-simulator.openapi.yaml`](../contracts/workday-raas-simulator.openapi.yaml).
It contains six operations, split across two explicit boundaries:

| Boundary | Operation | Purpose |
|---|---|---|
| Workday | `issueAccessToken` | Obtain the short-lived bearer token used by Dander. |
| Workday | `getWorkersReport` | Read the paged `Dander_Workers` custom report. |
| Workday | `getOrganizationsReport` | Read the paged `Dander_Organizations` custom report. |
| Simulator only | `setScenario` | Select one named deterministic failure. |
| Simulator only | `advanceDataset` | Introduce one worker update and one new worker. |
| Simulator only | `resetSimulator` | Restore normal behavior and the first generation. |

The report names, column aliases, `page`, `count`, and `updated_after` prompt aliases form the
Dander-to-tenant contract. A Workday administrator must create and secure those two reports before
the real-tenant acceptance. They are not claims about delivered Workday report names.

## Run locally

```bash
uv sync --extra dev
uv run python -m dander.dev.workday_simulator
```

The service binds to `127.0.0.1:8766` and prints synthetic credentials. FastAPI exposes the
contract at `http://127.0.0.1:8766/docs`. All fixtures are invented and packaged under
`src/dander/dev/fixtures/workday/`.

Select a failure with:

```bash
curl -X PUT http://127.0.0.1:8766/_dander/scenario \
  -H 'content-type: application/json' \
  -d '{"scenario":"throttling"}'
```

Supported scenarios are `expired_credentials`, `throttling`, `missing_permissions`, and
`malformed_record`. `throttling` fails the first workers request with 429 and then recovers;
`missing_permissions` denies only the organizations report; the malformed record violates the
declared worker Boolean contract without exposing a real row.

Run the contract tests against the live loopback service:

```bash
uv run pytest tests/integration/test_workday_simulator.py
```

## Later real-tenant acceptance

The simulator does not prove tenant configuration. One narrow acceptance must use a disposable or
sandbox Workday tenant and verify only these items:

1. Confirm the tenant's supported OAuth grant and token URL; do not assume the simulator settles
   tenant-specific authentication configuration.
2. Create the two web-service-enabled custom reports with the tracked aliases and least-privilege
   domain access for one integration user.
3. Read two pages, advance from a recorded `updated_at` boundary, and confirm no missing or
   duplicate business keys.
4. Revoke one required report permission and confirm Dander fails clearly, then restore it.
5. Store no tenant response, credential, or employee fixture in this repository.

Primary Workday references:

- [REST APIs in Apps and Integrations](https://developer.workday.com/documentation/GUID-6b063b57-9d85-474b-99b0-734d714652fd-enHYPHENus/RESTAPIsinAppsandIntegrations)
- [Accessing RaaS output](https://developer.workday.com/documentation/fdy1570549197818/ConceptAccessingRaaSOutput)
- [Integration and web-service limits](https://developer.workday.com/documentation/dan1370797408285/ReferenceIntegrationsandWebServiceLimits)
