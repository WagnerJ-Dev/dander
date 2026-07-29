"""Dander command-line entrypoint."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from click import ClickException
from rich.console import Console
from rich.table import Table

from dander.bootstrap import TerraformBootstrap, TerraformBootstrapError
from dander.core.config import Settings
from dander.ingestion import DltRestSource, Endpoint, load_source_config
from dander.runtime import PipelineRunner
from dander.sandbox import SandboxDataset, SandboxSafetyError
from dander.security import ApiKeyBasic, DefaultSecretStore, EnvironmentSecretStore
from dander.state import BigQueryWatermarkStore, SqliteWatermarkStore
from dander.writer import BigQueryReplaceWriter, BigQueryScd1Writer

if TYPE_CHECKING:
    from collections.abc import Sequence

app = typer.Typer(
    help="Dander — GCP-native data platform (ingest + transform + catalog).",
    no_args_is_help=True,
)
console = Console()
_SOURCE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_DEFAULT_CONNECTORS_DIR = Path("connectors")
_DEFAULT_INFRA_DIR = Path("infra")


@app.command()
def init(
    project: str = typer.Option(..., "--project", help="GCP project id."),
    state_bucket: str = typer.Option(
        ..., "--state-bucket", help="Existing GCS bucket for remote Terraform state."
    ),
    state_prefix: str = typer.Option(
        "dander/state", "--state-prefix", help="Object prefix for Terraform state."
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply the saved Terraform plan. Without this flag, only plan.",
    ),
    infra_dir: Path = typer.Option(_DEFAULT_INFRA_DIR, hidden=True),  # noqa: B008
) -> None:
    """Plan the BigQuery bootstrap; apply only with explicit confirmation."""
    if apply and not typer.confirm(
        f"Apply the Dander bootstrap to GCP project {project!r}?",
        default=False,
    ):
        raise typer.Abort()
    try:
        plan_path = TerraformBootstrap(infra_dir).execute(
            project=project,
            state_bucket=state_bucket,
            state_prefix=state_prefix,
            apply=apply,
        )
    except TerraformBootstrapError as error:
        raise ClickException(str(error)) from error

    action = "applied" if apply else "planned"
    console.print(f"[green]Bootstrap {action}.[/green] Saved plan: {plan_path}")


@app.command()
def run(
    source: str = typer.Argument(..., help="Source name from connectors/."),
    project: str | None = typer.Option(None, "--project", help="Override GCP_PROJECT_ID."),
    dataset: str | None = typer.Option(None, "--dataset", help="Override BQ_DATASET_RAW."),
    connectors_dir: Path = typer.Option(  # noqa: B008
        _DEFAULT_CONNECTORS_DIR, "--connectors-dir"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Validate config and print the execution plan without credentials or network calls.",
    ),
    sandbox: bool = typer.Option(
        False,
        "--sandbox",
        help="Require billing disabled and use no-DML, full-refresh sandbox storage.",
    ),
    state_path: Path = typer.Option(Path(".dander/state.db"), hidden=True),  # noqa: B008
) -> None:
    """Extract a configured source, write it, then commit endpoint watermarks."""
    if not _SOURCE_NAME.fullmatch(source):
        raise typer.BadParameter("Source names may contain only letters, numbers, '_' and '-'")

    config = load_source_config(connectors_dir / f"{source}.yaml")
    if config.name != source:
        raise ClickException(f"Connector file declares source {config.name!r}, expected {source!r}")
    settings = Settings()
    resolved_project = project or settings.gcp_project_id
    resolved_dataset = dataset or settings.bq_dataset_raw

    if dry_run:
        _print_plan(
            config.name,
            resolved_project,
            resolved_dataset,
            config.endpoints,
            sandbox=sandbox,
        )
        return
    if not resolved_project:
        raise ClickException("GCP project is required via --project or GCP_PROJECT_ID")

    if config.auth_strategy != "api_key_basic":
        raise ClickException(f"Unsupported auth strategy for v0: {config.auth_strategy!r}")

    if sandbox:
        try:
            SandboxDataset().prepare(resolved_project, resolved_dataset)
        except SandboxSafetyError as error:
            raise ClickException(str(error)) from error

    secrets = EnvironmentSecretStore() if sandbox else DefaultSecretStore()
    auth = ApiKeyBasic(secrets, config.auth_ref)
    rest_source = DltRestSource(config, auth)
    result = PipelineRunner(
        source=rest_source,
        writer=(
            BigQueryReplaceWriter(project=resolved_project)
            if sandbox
            else BigQueryScd1Writer(project=resolved_project)
        ),
        watermarks=(
            SqliteWatermarkStore(state_path)
            if sandbox
            else BigQueryWatermarkStore(
                project=resolved_project,
                dataset=resolved_dataset,
            )
        ),
        project=resolved_project,
        dataset=resolved_dataset,
        resume_from_watermark=not sandbox,
    ).run()

    table = Table(title=f"Dander run {result.run_id}")
    table.add_column("Endpoint")
    table.add_column("Extracted", justify="right")
    table.add_column("Affected", justify="right")
    table.add_column("Cursor committed")
    for endpoint in result.endpoints:
        table.add_row(
            endpoint.endpoint,
            str(endpoint.extracted),
            str(endpoint.affected),
            "yes" if endpoint.committed_cursor is not None else "no",
        )
    console.print(table)


def _print_plan(
    source: str,
    project: str,
    dataset: str,
    endpoints: Sequence[Endpoint],
    *,
    sandbox: bool = False,
) -> None:
    """Render a credential-free execution plan."""
    table = Table(title=f"Dander dry run: {source}")
    table.add_column("Endpoint")
    table.add_column("Target")
    table.add_column("Mode")
    for endpoint in endpoints:
        name = endpoint.name
        mode = "REPLACE (sandbox)" if sandbox else "SCD1"
        table.add_row(str(name), f"{project or '<unset>'}.{dataset}.{source}_{name}", mode)
    console.print(table)


if __name__ == "__main__":
    app()
