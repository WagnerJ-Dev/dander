# Secret Manager module

Creates named, automatically replicated Secret Manager containers and optional per-secret runtime
access bindings. It intentionally does not manage secret versions or values, keeping credentials
out of Terraform configuration, plans, and state.
