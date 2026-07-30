# Cost guard module

Packages the tested Python handler and deploys it as a Pub/Sub-triggered Gen 2 Cloud Run function.
It creates a project-only budget with 80% and 100% thresholds and regular Pub/Sub updates.

Simulation is the default. Live mode can unlink billing once reported cost reaches the budget,
which stops services and can delete resources. Billing data and notifications are delayed, so this
is not a hard spending cap. Cloud Build, Cloud Run functions, Cloud Storage, and Artifact Registry
are billable services even when usage may fit within free allowances.

A dedicated build identity carries the Cloud Build builder and Cloud Run invoker roles required by
Google's Gen 2 deployment path and can read objects only from the supplied source bucket.
