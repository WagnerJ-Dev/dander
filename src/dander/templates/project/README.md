# My Dander Project

This project was created by `dander new`. It starts with one paused, credential-free Greenhouse
Job Board pipeline so infrastructure changes remain reviewable before any schedule is enabled.

> **Alpha:** review Dander's
> [known limitations](https://github.com/harrisonoconnorhover/dander/blob/main/docs/known-limitations.md)
> and use a disposable GCP project. Only the latest patch in the current `0.x` minor is supported.

```bash
dander validate
dander run greenhouse_jobs --dry-run --project YOUR_GCP_PROJECT
dander init --project YOUR_GCP_PROJECT --container-image REGION-docker.pkg.dev/PROJECT/dander/dander@sha256:DIGEST
```

`dander init` plans by default. Review the saved Terraform plan before using `--apply`. The starter
manifest keeps its scheduler paused and does not enable Dander's optional managed cost guard.
Disabling the guard does not prevent or cap cloud charges.

Use the public [hosted Greenhouse quickstart](https://github.com/harrisonoconnorhover/dander/blob/main/docs/getting-started.md)
for the complete installation, provisioning, manual-run, and schedule-enablement sequence. Follow
the [upgrade guide](https://github.com/harrisonoconnorhover/dander/blob/main/docs/upgrading.md)
before changing the pinned `DANDER_VERSION` in this project's Dockerfile.

To host Druff's compiled interface with this platform, also pass its immutable image as
`--druff-container-image`. Repeat that input on later full-platform plans to retain the service.
The public UI stores no graph or credentials; start `dander graph serve --origin HTTPS_DRUFF_URL`
from this project when you want the browser to open, save, or run one operator-bound graph.

`graphs/greenhouse_jobs.yaml` is an inactive Druff-compatible example. To make a pipeline execute
that graph instead of SQL models, set its manifest entry to:

```yaml
source: greenhouse_job_board
graph: graphs/greenhouse_jobs.yaml
models: []
build_models: false
```

The graph reuses `connectors/greenhouse_job_board.yaml`; it never stores API or authentication
settings itself. Review the graph target before planning or running it.
