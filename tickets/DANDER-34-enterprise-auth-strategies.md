---
id: DANDER-34
title: Implement OAuth2 JWT and OAuth1 TBA authentication
status: complete
component: security
epic: runtime
depends_on: [DANDER-1]
created: 2026-07-29
---

## Acceptance Criteria

- [x] OAuth2 JWT resolves issuer/key references only when needed, signs a short-lived assertion,
      exchanges it at an HTTPS endpoint, and caches the bearer token before declared/default expiry.
- [x] OAuth1 TBA signs method, base URI, query, and OAuth parameters with HMAC-SHA256 for every
      request using freshly resolved credential references.
- [x] Nonces, clocks, signing, and token transport are injected for deterministic offline tests.
- [x] Connector validation and CLI dispatch require the exact references/options for each strategy.
- [x] Errors never contain a private key, client secret, token secret, assertion, or access token.
- [x] Public exports, documentation, strict typing, tests, and full checks pass.

## Review Log

OAuth1 follows RFC 5849 percent-encoding and normalized parameter ordering while using NetSuite's
HMAC-SHA256 profile. OAuth2 JWT uses Google Auth's RSA signer by default and never persists its
assertion or resolved signing key.
