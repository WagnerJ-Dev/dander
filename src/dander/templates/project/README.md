# My Dander Project

This project was created by `dander new`. It starts with one paused, credential-free Greenhouse
Job Board pipeline so infrastructure changes remain reviewable before any schedule is enabled.

```bash
dander validate
dander run greenhouse_jobs --dry-run --project YOUR_GCP_PROJECT
dander init --project YOUR_GCP_PROJECT --container-image REGION-docker.pkg.dev/PROJECT/dander/dander@sha256:DIGEST
```

`dander init` plans by default. Review the saved Terraform plan before using `--apply`. The starter
manifest requires the guarded free-tier preflight and keeps its scheduler paused.
