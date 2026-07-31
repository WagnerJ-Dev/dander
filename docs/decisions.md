# Engineering Decisions

## 2026-07-31 — Fork-owned CI and evidence surface

- The admin-owned `harrisonoconnorhover/dander` fork is the execution surface for CI, protected
  environments, and retained workflow evidence; upstream `WagnerJ-Dev/dander` remains the
  contribution and review record through PR #1.
- Moving the branch preserves commit identities, including `8dfdd92`. Only repository-scoped
  objects—pull requests, check runs, environments, secrets, and workflow URLs—are re-anchored.
- GitHub OIDC Workload Identity Federation must be reconfigured for the fork's exact repository
  and ref before any live proof is dispatched. No cloud mutation is implied by this decision.

## 2026-07-31 — Stage-zero state retention

- `infra/bootstrap-admin` retains only migration input and recovery material in secured,
  operator-managed local storage; its active bootstrap state is held in the permanent GCS backend.
  Operators must keep local state and backups encrypted and access-controlled outside the repository.
- The created platform-state bucket is versioned, non-public, uniformly access-controlled, and
  non-destructive (`force_destroy = false`); prior object generations are retained for recovery and
  are not removed by routine migrations.

## 2026-07-31 — Permanent stage-zero GCS backend

- `infra/bootstrap-admin` uses the existing GCS bucket with the fixed
  `dander/bootstrap-admin/state` prefix as its permanent backend; the platform root continues to
  use `dander/state`.
- The backend is partial by design: bucket and prefix are supplied at initialization, while
  credentials come from the operator's authenticated Google context and never enter Terraform
  configuration.
- Local stage-zero state is migration input and recovery material only. Object Versioning and GCS
  locking must be verified before migration, and state, plans, backups, secrets, raw HubSpot
  responses, and `.terraform/` contents remain outside GitHub.

## 2026-07-30 — Reproducible bootstrap verification

- Terraform creates a distinct `dander-bootstrap` identity for approved infrastructure runs. Its
  broader provisioning roles are never attached to Cloud Run, Scheduler, or GitHub WIF; workloads
  use the narrow runtime and scheduler identities instead.
- Terraform state is always initialized through the GCS backend. `dander verify deployment` reads
  the initialized backend metadata, pulls state read-only to prove reachability, and checks actual
  Google Cloud resources rather than trusting Terraform output.
- Verification writes a sanitized JSON artifact. Failed checks remain explicit and make the command
  fail, so evidence cannot claim a successful deployment after a partial bootstrap.

## 2026-07-29 — Bootstrap credentials and deployment identity

- Terraform creates Secret Manager containers and IAM bindings, but never secret versions or
  values. Operators add values out of band so credentials cannot enter plans or remote state.
- GitHub deployment uses OIDC Workload Identity Federation constrained to one repository and exact
  ref. The federated principal can impersonate only a dedicated deployer; that deployer writes only
  Dander's Artifact Registry repository and can act as only Dander's runtime accounts.
- Hosted runtime plans require an immutable image digest and billing account. Planning remains the
  CLI default, and applying still uses the exact saved plan after interactive confirmation.

## 2026-07-29 — Simulation-first integrated cost guard

- The bootstrap can package the tested handler and provision its project budget, Pub/Sub topic,
  least-privilege identity, and Gen 2 function, but the entire module remains opt-in.
- Simulation is the default. Live billing detachment requires `--live-cost-guard`, a reviewed saved
  plan, and confirmation that explicitly names the destructive behavior.
- Budget notifications are delayed and not a spending cap. Function deployment uses billable GCP
  services, so its plan is never represented as guaranteeing a zero-dollar outcome.

## 2026-07-29 — BigQuery history and append semantics

- Incremental batches use cursor validation plus SCD1 key merge; extraction and watermark state
  own the lower bound, while the writer owns rerun idempotence.
- Snapshots never update/delete history. They use a configured date/timestamp partition and
  suppress exact rows both across reruns and within one incoming batch.
- SCD2 computes changed rows once, then closes and inserts versions in one transaction. System
  columns are reserved and nested values compare through canonical BigQuery JSON rendering.

## 2026-07-29 — Incremental transform boundary

- Incremental model metadata explicitly names its unique key and cursor; these are never inferred
  from generic tests or column naming conventions.
- Builds include rows at or above the existing maximum cursor, deduplicate each key by latest
  cursor, and `MERGE`. Re-reading the boundary handles tied timestamps without losing rows and is
  safe because the merge is idempotent; canonical JSON is the deterministic final tie-breaker.

## 2026-07-29 — Concrete enterprise ingestion proof

- Workday RaaS is the first hand-rolled `EnterpriseSource`: connector config selects it explicitly,
  while downstream runtime/writer/state code continues depending only on `Source`.
- Response envelopes, page progression, cursor params, bounded retry/backoff, and scalar casts are
  owned by this path. Transport and sleeping are injected so tests use no tenant or credential.
- Schema discovery returns declarations only. Cast failures expose field/type contract names but
  never rejected row values.

## 2026-07-29 — Visual graph execution boundary

- Linear source-to-transform-to-target mappings compile to explicit-column BigQuery SQL. Scalar
  expressions are parsed and allow-listed; custom transformations resolve only through a trusted
  built-in registry, never `eval`, imports, or inline code.
- Target configuration now dispatches every declared write mode to its concrete idempotent writer.
- Join execution remains fail-closed because the current edge schema makes its target both the
  right join input and output. A distinct join-output node is required before execution is safe.

## 2026-07-29 — Enterprise authentication profiles

- OAuth2 JWT assertions use a secret-backed RSA key only during token acquisition. Tokens cache to
  the provider expiry or a conservative 300-second default for providers such as Salesforce that
  omit `expires_in`.
- OAuth1 TBA signs every method, base URI, query, and OAuth parameter using RFC 5849 normalization
  and NetSuite's HMAC-SHA256 profile; all four credentials are resolved fresh per request.
- Connector files contain only secret references. Signing, token transport, nonce, and clocks are
  injectable so the complete behavior is proven offline.

## 2026-07-29 — Executable join output

- An executable join belongs to a transform node that explicitly names its two predecessor inputs;
  the transform is the distinct output relation. Its two incoming edges own output-field mappings.
- The edge-level join shape remains loadable for compatibility but non-executable because its
  target cannot safely represent both a right input and output.
- Join SQL uses declared equality keys, explicit projected columns, and the same safe expression
  compiler as linear mappings.

## 2026-07-29 — Operational run history

- Pipeline runs record start and terminal status plus endpoint/row-count aggregates in the control
  plane: BigQuery for guarded/cloud execution and the existing SQLite file for sandbox execution.
- History never stores rows, cursors, credentials, assertions, or exception text. A history-update
  failure during pipeline failure is logged without masking the original pipeline exception.

## 2026-07-29 — Bounded BigQuery load jobs

- Every writer accepts a validated `max_batch_rows` contract (10,000 by default, 100,000 maximum
  in target config). One logical batch is validated/deduplicated before requests are split.
- The first load request truncates its destination and later chunks append, preserving replacement
  and unique-staging semantics without unbounded request payloads.

## 2026-07-29 — Controlled schema evolution

- Target-node fields become the writer's declared schema. Strict mode remains the default;
  additive mode emits idempotent nullable additions for supported BigQuery scalar types only.
- Additive evolution never drops columns, changes types/modes, or infers nested structures.
  Invalid and duplicate declarations fail before a load request.

## 2026-07-29 — Storage Write API workload path

- Load jobs remain the default for latency-insensitive batch work. Keyed SCD1/incremental targets
  can explicitly select `storage_write`.
- Storage Write uses an offset-checked pending stream into a uniquely named staging table,
  finalizes and atomically commits it, then runs the existing idempotent merge. Direct final-table
  streaming was rejected because a new stream on rerun could duplicate rows.
- The Python protobuf encoder supports the scalar types it can represent without ambiguous custom
  annotations; unsupported types fail before any staging mutation.

## 2026-07-29 — Hosted public pipeline tail

- The scheduled public connector builds and catalogs only `stg_greenhouse__jobs`; selecting this
  root avoids coupling a credential-free run to private Harvest candidate data.
- Transform tests run before the semantic registry is written. A failed ingestion or transform
  prevents all later publication.
- Local registry compilation is the hosted default. Dataplex storage requires an explicit
  bootstrap flag that separately enables its API and runtime IAM.

## 2026-07-29 — Standard REST source rate control

- A dlt connector with a rate policy receives a private session that applies token-bucket pacing,
  safe-read-only retries, and fixed or exponential backoff; connectors without a policy retain
  dlt's default session.
- Marketo's official client-credential query placement is supported explicitly while API calls
  continue using bearer headers. Connector files still contain references and tenant placeholders,
  never credential values.

## 2026-07-30 — Sensitive-system scope is hypothetical

- Workday, Xactly, Salesforce, NetSuite, and similar systems are target connector categories, not
  evidence that Dander derives from, connects to, or contains data from an existing company.
- Do not infer employer ownership, regulated-company affiliation, customer records, or HR records
  from the architecture note. Apply normal provenance and privacy review only when actual
  employer-owned material, credentials, or non-public data enters scope.

## 2026-07-30 — Deterministic synthetic vendor proof

- A loopback-only invented API is the default integration proof for Dander-controlled REST
  behavior; it contains no tenant identifiers, credentials, or copied vendor records.
- Cursor and Link pagination, duplicates, updates, and retryable failures are deterministic so the
  real dlt HTTP boundary can be validated repeatably without a vendor contract or cloud mutation.
- The packaged server proves extraction only. The normal CLI retains its explicit BigQuery write
  boundary rather than introducing a second local production storage mode for a demo.

## 2026-07-30 — Public data versus controlled test data

- Greenhouse remains the primary live demo; Lever and Ashby broaden real public response and
  pagination coverage without credentials or non-public records.
- Synthetic endpoints remain necessary for deliberate duplicates, updates, throttling, and server
  failures because public providers must not be manipulated to produce test failures.
- Candidate/contact-shaped tests use invented records in an owned test account. Public profiles are
  not treated as a substitute candidate dataset.
