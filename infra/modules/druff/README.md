# Druff Cloud Run service

Hosts Druff's compiled, source-free interface beside Dander's hosted runtime on a public
scale-to-zero Cloud Run service. The hosted runtime owns Cloud Run API enablement, so this module
does not create a second Terraform owner for that project service. Its dedicated service account
receives no project roles, secrets, datasets, or runtime authority.

Cloud Run's default minimum of zero remains implicit. Terraform ignores the provider-only top-level
scaling status, while the authored template maximum and every other service setting remain managed.

The browser still connects to the operator-owned Dander graph service on `127.0.0.1`; no graph,
credential, manifest, or execution API is hosted by this module.
