"""Dander CLI entrypoint.

``dander init`` provisions the GCP data platform via Terraform; ``dander run`` extracts a source
and loads it to BigQuery using its configured write pattern.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    help="Dander — GCP-native data platform (ingest + transform + catalog).",
    no_args_is_help=True,
)


@app.command()
def init() -> None:
    """Provision the GCP data platform (Secret Manager, IAM/WIF, Cloud Run, BigQuery) via Terraform."""
    raise NotImplementedError("DANDER: wrap `terraform apply` over infra/ (see infra/README.md)")


@app.command()
def run(source: str = typer.Argument(..., help="Source name from connectors/")) -> None:
    """Extract a source and load it to BigQuery using its configured write pattern."""
    raise NotImplementedError("DANDER: wire ingestion -> writer -> state for the given source")


if __name__ == "__main__":
    app()
