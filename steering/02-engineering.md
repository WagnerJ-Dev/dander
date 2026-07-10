# Engineering Steering — cross-cutting principles

> Language-agnostic rules for how we design and build. Language specifics live in `languages/`.

## Design: interfaces first, providers behind them

This platform lives or dies on clean abstractions. The whole architecture is **adapter/strategy**:
one interface, swappable implementations.

- `AuthStrategy`, `SecretStoreProvider`, `ComputeProvider`, `Source`, `WritePattern` — application
  code depends on the **interface**, never a concrete cloud/system.
- GCP implementation now; AWS/Azure later must be "add an implementation," not "rewrite callers."
- Favor **composition over inheritance**. Keep interfaces small (ISP). Depend on abstractions (DIP).
- Single Responsibility per class/module. Open for extension (new strategy) without modifying callers.

## Config-driven over code-driven

- A new source/connector should be a **config object**, not new code, wherever possible.
- Keep behavior declarative (endpoints, pagination style, cursor field, field mappings in config);
  reserve code for genuinely novel logic.

## Idempotency & state (this is a data platform)

- Every pipeline run must be **safely re-runnable**. Restarts must not duplicate or corrupt data.
- Track a **watermark/cursor per source+entity** in a control table; resume from last success.
- Writes use explicit patterns (SCD1/SCD2/snapshot/incremental) — never ad-hoc mutation.

## Error handling & observability

- Fail loud with actionable context; never swallow exceptions silently.
- **Never** put secrets or sensitive row data in logs or exception messages.
- Rate-limit/backoff per source (Marketo & Salesforce throttle). Retries are bounded and logged.
- Structured logging; each run has a traceable id.

## Testing

- Business logic (auth strategies, type casting, MERGE builders, DAG resolution) is unit-tested.
- No network in unit tests — mock external APIs; fixtures carry **no** real/sensitive data.
- A change without tests for its logic is incomplete. PR-review checks this.

## Version control & tickets

- Small, focused commits with imperative messages (`Add OAuth1 TBA strategy`).
- Work is tracked as tickets in `tickets/` (see `tickets/README.md`). Every code change traces
  to a ticket; the ticket's acceptance criteria are the definition of done.
- Never commit generated secrets, state, or `.env`.

## Dependency & borrow-vs-build

- The differentiated layers (Security, Writer, Transform) we own. Undifferentiated plumbing
  (pagination/retry/schema-evolution) may lean on a vetted library if the Decision Log records why.
- Pin versions; minimize surface area; justify every new dependency.
