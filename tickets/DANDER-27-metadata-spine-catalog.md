---
id: DANDER-27
title: Project model metadata into catalog and semantics
status: done
component: python
epic: catalog
depends_on: [DANDER-26]
created: 2026-07-29
---

## Context

The upstream architecture names the single metadata spine as a core differentiator: one model YAML
must drive SQL, Dataplex catalog aspects, and a semantic/agent registry. DANDER-26 consumes that
YAML for transforms and tests, but catalog publication remains an abstract stub.

## Acceptance Criteria

- [x] A canonical, immutable catalog asset derives deterministically from each selected model and
      includes relation, lineage, ownership, sensitivity, columns, materialization, and test contract.
- [x] A local semantic registry is written atomically as stable, versioned JSON with no credentials,
      timestamps, or sensitive row values.
- [x] Dataplex system-aspect payloads for overview, contacts, schema, and generic metadata derive
      from the same canonical asset.
- [x] An optional Dataplex publisher targets the system BigQuery entry through `modifyEntry`,
      updates only generated aspect keys, and never deletes unrelated aspects.
- [x] `dander catalog` compiles locally by default and requires an explicit publish flag for cloud
      mutation; selected models include their dependencies.
- [x] The Greenhouse jobs metadata compiles to a validated registry and Dataplex request in tests.
- [x] Documentation, handoff, linting, formatting, strict typing, and the full test suite pass.

## Design

Keep the metadata spine cloud-neutral and deterministic. Put Dataplex request construction behind a
small publisher protocol. Use reusable system aspects instead of creating custom aspect types. The
local registry is always produced first and remains useful without billing or cloud access.

## Review Log

PASS — the real Greenhouse model produces byte-stable semantic JSON and four validated reusable
system aspects; request tests prove the BigQuery system entry, aspect-only update mask, explicit
keys, and non-deleting behavior; read-only live lookup resolved the expected catalog entry; 348
tests and all repository checks pass. Live aspect storage remains intentionally opt-in and unspent.
