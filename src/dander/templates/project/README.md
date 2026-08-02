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
manifest requires the guarded free-tier preflight and keeps its scheduler paused.

Use the public [hosted Greenhouse quickstart](https://github.com/harrisonoconnorhover/dander/blob/main/docs/getting-started.md)
for the complete installation, provisioning, manual-run, and schedule-enablement sequence. Follow
the [upgrade guide](https://github.com/harrisonoconnorhover/dander/blob/main/docs/upgrading.md)
before changing the pinned `DANDER_VERSION` in this project's Dockerfile.
