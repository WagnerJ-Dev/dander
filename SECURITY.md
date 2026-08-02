# Security Policy

Dander is alpha software. Use a dedicated GCP project, least-privilege credentials, immutable
container digests, and reviewed Terraform plans. Never put provider tokens, Terraform state, raw
source rows, or recovery codes in an issue or pull request.

## Supported versions

Only the newest published patch of the current `0.x` minor receives security and correctness fixes.
Before `0.1.0` is published, the newest `0.1.0` release candidate is supported. After a final or a
newer patch is published, superseded candidates and patches are unsupported and should be upgraded.

| Version | Supported |
|---|---|
| Newest `0.1.x` patch, or current `0.1.0` candidate before final | Yes |
| Superseded `0.1.x` patch or candidate | No |
| `0.0.x` and older | No |

Support for `0.1.x` ends when `0.2.0` is published. This policy does not promise a response or fix
deadline.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/harrisonoconnorhover/dander/security/advisories/new).
Include the affected Dander version, impact, reproduction using invented data, and any mitigation.
Do not open a public issue until disclosure has been coordinated.

Ordinary bugs that contain no sensitive security detail belong in the public
[issue tracker](https://github.com/harrisonoconnorhover/dander/issues).
