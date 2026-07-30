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
from dander.catalog import (
    CatalogPublishError,
    DataplexCatalogPublisher,
    MetadataSpine,
    SemanticRegistryError,
    SemanticRegistryPublisher,
)
from dander.core.config import Settings
from dander.ingestion import (
    DltRestSource,
    Endpoint,
    IngestionEngine,
    SourceConfig,
    WorkdayRaasSource,
    load_source_config,
)
from dander.runtime import PipelineRunner
from dander.sandbox import GuardedFreeTierVerifier, SandboxDataset, SandboxSafetyError
from dander.security import (
    ApiKeyBasic,
    AuthStrategy,
    DefaultSecretStore,
    EnvironmentSecretStore,
    NoAuth,
    OAuth1TBA,
    OAuth2ClientCredentials,
    OAuth2JWT,
)
from dander.state import BigQueryWatermarkStore, SqliteWatermarkStore
from dander.transform import (
    BigQueryTransformRunner,
    TransformProject,
    TransformProjectError,
    TransformRunError,
)
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
_DEFAULT_MODELS_DIR = Path("models")
_DEFAULT_CATALOG_PATH = Path(".dander/catalog.json")


@app.command()
def init(
    project: str = typer.Option(..., "--project", help="GCP project id."),
    state_bucket: str = typer.Option(
        ..., "--state-bucket", help="Existing GCS bucket for remote Terraform state."
    ),
    state_prefix: str = typer.Option(
        "dander/state", "--state-prefix", help="Object prefix for Terraform state."
    ),
    region: str = typer.Option("us-central1", "--region", help="GCP region."),
    bigquery_location: str = typer.Option(
        "US", "--bigquery-location", help="BigQuery dataset location."
    ),
    enable_runtime: bool = typer.Option(
        False,
        "--enable-runtime",
        help="Provision the scheduled Cloud Run ingestion runtime.",
    ),
    billing_account_id: str = typer.Option(
        "",
        "--billing-account",
        help="Billing account required by the guarded runtime.",
    ),
    container_image: str = typer.Option(
        "",
        "--container-image",
        help="Immutable Artifact Registry image reference ending in @sha256 digest.",
    ),
    scheduler_paused: bool = typer.Option(
        True,
        "--scheduler-paused/--scheduler-enabled",
        help="Keep the daily scheduler paused until a manual run succeeds.",
    ),
    secret_ids: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--secret-id",
        help="Create a Secret Manager container without a value. Repeat for multiple secrets.",
    ),
    github_repository: str = typer.Option(
        "",
        "--github-repository",
        help="GitHub owner/repository allowed to deploy using keyless OIDC.",
    ),
    github_ref: str = typer.Option(
        "refs/heads/main",
        "--github-ref",
        help="Exact branch or tag ref allowed to deploy.",
    ),
    enable_cost_guard: bool = typer.Option(
        False,
        "--enable-cost-guard",
        help="Provision the project budget and simulation-first kill switch.",
    ),
    cost_guard_budget_name: str = typer.Option(
        "dander-sbx-cap",
        "--cost-guard-budget-name",
        help="Exact project budget display name.",
    ),
    cost_guard_budget_amount: str = typer.Option(
        "5.00",
        "--cost-guard-budget-amount",
        help="USD project budget amount; maximum 5.00.",
    ),
    live_cost_guard: bool = typer.Option(
        False,
        "--live-cost-guard",
        help="Allow the cost guard to unlink billing. Destructive; simulation is the default.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply the saved Terraform plan. Without this flag, only plan.",
    ),
    infra_dir: Path = typer.Option(_DEFAULT_INFRA_DIR, hidden=True),  # noqa: B008
) -> None:
    """Plan the GCP bootstrap; apply only with explicit confirmation."""
    confirmation = f"Apply the Dander bootstrap to GCP project {project!r}?"
    if live_cost_guard:
        confirmation = f"{confirmation[:-1]} with LIVE automatic billing detachment enabled?"
    if apply and not typer.confirm(
        confirmation,
        default=False,
    ):
        raise typer.Abort()
    try:
        plan_path = TerraformBootstrap(infra_dir).execute(
            project=project,
            state_bucket=state_bucket,
            state_prefix=state_prefix,
            apply=apply,
            region=region,
            bigquery_location=bigquery_location,
            enable_runtime=enable_runtime,
            billing_account_id=billing_account_id,
            container_image=container_image,
            scheduler_paused=scheduler_paused,
            secret_ids=tuple(secret_ids or ()),
            github_repository=github_repository,
            github_ref=github_ref,
            enable_cost_guard=enable_cost_guard,
            cost_guard_budget_name=cost_guard_budget_name,
            cost_guard_budget_amount=cost_guard_budget_amount,
            live_cost_guard=live_cost_guard,
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
    guarded_free_tier: bool = typer.Option(
        False,
        "--guarded-free-tier",
        help="Require billing plus a <=$5 budget guard before using the production GCP path.",
    ),
    budget_name: str = typer.Option("dander-sbx-cap", "--budget-name", hidden=True),
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
    if sandbox and guarded_free_tier:
        raise ClickException("--sandbox and --guarded-free-tier are mutually exclusive")

    if dry_run:
        _print_plan(
            config.name,
            resolved_project,
            resolved_dataset,
            config.endpoints,
            sandbox=sandbox,
            guarded_free_tier=guarded_free_tier,
        )
        return
    if not resolved_project:
        raise ClickException("GCP project is required via --project or GCP_PROJECT_ID")

    if sandbox:
        try:
            SandboxDataset().prepare(resolved_project, resolved_dataset)
        except SandboxSafetyError as error:
            raise ClickException(str(error)) from error
    elif guarded_free_tier:
        try:
            GuardedFreeTierVerifier().require_guarded(
                resolved_project,
                budget_name=budget_name,
            )
        except SandboxSafetyError as error:
            raise ClickException(str(error)) from error

    secrets = EnvironmentSecretStore() if sandbox else DefaultSecretStore()
    auth = _build_auth(config, secrets)
    source_adapter = (
        WorkdayRaasSource(config, auth)
        if config.engine is IngestionEngine.WORKDAY_RAAS
        else DltRestSource(config, auth)
    )
    result = PipelineRunner(
        source=source_adapter,
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


@app.command()
def build(
    project: str | None = typer.Option(None, "--project", help="Override GCP_PROJECT_ID."),
    selected: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--select",
        help="Build one model and its model dependencies. Repeat to select multiple models.",
    ),
    models_dir: Path = typer.Option(_DEFAULT_MODELS_DIR, "--models-dir"),  # noqa: B008
    guarded_free_tier: bool = typer.Option(
        False,
        "--guarded-free-tier",
        help="Require the <=$5 budget guard before submitting BigQuery queries.",
    ),
    budget_name: str = typer.Option("dander-sbx-cap", "--budget-name", hidden=True),
) -> None:
    """Build selected SQL models in dependency order and run their data tests."""
    resolved_project = project or Settings().gcp_project_id
    if not resolved_project:
        raise ClickException("GCP project is required via --project or GCP_PROJECT_ID")
    _require_transform_guard(
        resolved_project,
        guarded_free_tier=guarded_free_tier,
        budget_name=budget_name,
    )
    try:
        result = BigQueryTransformRunner(project=resolved_project).build(
            models_dir,
            selected=selected,
        )
    except (TransformProjectError, TransformRunError) as error:
        raise ClickException(str(error)) from error
    _print_transform_result("Built", result.models, result.assertions)


@app.command("test")
def test_models(
    project: str | None = typer.Option(None, "--project", help="Override GCP_PROJECT_ID."),
    selected: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--select",
        help="Test one model and its model dependencies. Repeat to select multiple models.",
    ),
    models_dir: Path = typer.Option(_DEFAULT_MODELS_DIR, "--models-dir"),  # noqa: B008
    guarded_free_tier: bool = typer.Option(
        False,
        "--guarded-free-tier",
        help="Require the <=$5 budget guard before submitting BigQuery queries.",
    ),
    budget_name: str = typer.Option("dander-sbx-cap", "--budget-name", hidden=True),
) -> None:
    """Run declared generic tests against existing model relations."""
    resolved_project = project or Settings().gcp_project_id
    if not resolved_project:
        raise ClickException("GCP project is required via --project or GCP_PROJECT_ID")
    _require_transform_guard(
        resolved_project,
        guarded_free_tier=guarded_free_tier,
        budget_name=budget_name,
    )
    try:
        result = BigQueryTransformRunner(project=resolved_project).test(
            models_dir,
            selected=selected,
        )
    except (TransformProjectError, TransformRunError) as error:
        raise ClickException(str(error)) from error
    _print_transform_result("Tested", result.models, result.assertions)


@app.command()
def catalog(
    project: str | None = typer.Option(None, "--project", help="Override GCP_PROJECT_ID."),
    selected: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--select",
        help="Catalog one model and its dependencies. Repeat to select multiple models.",
    ),
    models_dir: Path = typer.Option(_DEFAULT_MODELS_DIR, "--models-dir"),  # noqa: B008
    output: Path = typer.Option(_DEFAULT_CATALOG_PATH, "--output"),  # noqa: B008
    publish_dataplex: bool = typer.Option(
        False,
        "--publish-dataplex",
        help="Attach generated aspects to BigQuery catalog entries; may incur metadata storage.",
    ),
    location: str = typer.Option(
        "us",
        "--location",
        help="Dataplex location for the BigQuery system entry.",
    ),
    guarded_free_tier: bool = typer.Option(
        False,
        "--guarded-free-tier",
        help="Require the <=$5 budget guard before Dataplex publication.",
    ),
    budget_name: str = typer.Option("dander-sbx-cap", "--budget-name", hidden=True),
) -> None:
    """Compile model metadata into a local registry and optionally publish Dataplex aspects."""
    resolved_project = project or Settings().gcp_project_id
    if not resolved_project:
        raise ClickException("GCP project is required via --project or GCP_PROJECT_ID")
    try:
        transform_project = TransformProject.load(models_dir, project_id=resolved_project)
        assets = MetadataSpine().compile(transform_project, selected=selected)
        manifest = MetadataSpine().manifest(assets)
        registry_path = SemanticRegistryPublisher().publish(manifest, output)
    except (SemanticRegistryError, TransformProjectError) as error:
        raise ClickException(str(error)) from error

    published = 0
    if publish_dataplex:
        _require_transform_guard(
            resolved_project,
            guarded_free_tier=guarded_free_tier,
            budget_name=budget_name,
        )
        try:
            publisher = DataplexCatalogPublisher(
                project=resolved_project,
                location=location,
            )
            for asset in assets:
                publisher.publish(asset)
                published += 1
        except CatalogPublishError as error:
            raise ClickException(str(error)) from error

    console.print(
        f"[green]Cataloged {len(assets)} model(s) in {registry_path}; "
        f"published {published} Dataplex entr{'y' if published == 1 else 'ies'}.[/green]"
    )


def _require_transform_guard(
    project: str,
    *,
    guarded_free_tier: bool,
    budget_name: str,
) -> None:
    if not guarded_free_tier:
        return
    try:
        GuardedFreeTierVerifier().require_guarded(project, budget_name=budget_name)
    except SandboxSafetyError as error:
        raise ClickException(str(error)) from error


def _print_transform_result(action: str, models: Sequence[str], assertions: int) -> None:
    table = Table(title=f"Dander transform: {action.lower()}")
    table.add_column("Model")
    for model in models:
        table.add_row(model)
    console.print(table)
    summary = f"{action} {len(models)} model(s); {assertions} assertion(s) passed."
    console.print(f"[green]{summary}[/green]")


def _build_auth(
    config: SourceConfig,
    secrets: DefaultSecretStore | EnvironmentSecretStore,
) -> AuthStrategy:
    """Construct a supported authentication strategy from validated connector metadata."""
    if config.auth_strategy == "none":
        return NoAuth()
    if config.auth_strategy == "api_key_basic":
        if config.auth_ref is None:
            raise ClickException("api_key_basic connector is missing auth_ref")
        return ApiKeyBasic(secrets, config.auth_ref)
    if config.auth_strategy == "oauth2_client_credentials":
        token_url = config.auth_options["token_url"]
        subject = config.auth_options.get("subject")
        if not isinstance(token_url, str):
            raise ClickException("OAuth token_url must be a string")
        if subject is not None and (isinstance(subject, bool) or not isinstance(subject, int)):
            raise ClickException("OAuth subject must be an integer Greenhouse user id")
        return OAuth2ClientCredentials(
            secrets,
            client_id_ref=config.auth_refs["client_id"],
            client_secret_ref=config.auth_refs["client_secret"],
            token_url=token_url,
            subject=subject,
        )
    if config.auth_strategy == "oauth2_jwt":
        subject = config.auth_options.get("subject")
        if subject is not None and not isinstance(subject, str):
            raise ClickException("OAuth JWT subject must be a string")
        scope = config.auth_options.get("scope")
        if scope is not None and not isinstance(scope, str):
            raise ClickException("OAuth JWT scope must be a string")
        default_expires_in = config.auth_options.get("default_expires_in", 300)
        if isinstance(default_expires_in, bool) or not isinstance(default_expires_in, int):
            raise ClickException("OAuth JWT default_expires_in must be an integer")
        return OAuth2JWT(
            secrets,
            issuer_ref=config.auth_refs["issuer"],
            private_key_ref=config.auth_refs["private_key"],
            token_url=str(config.auth_options["token_url"]),
            scope=scope,
            subject=subject,
            default_expires_in=default_expires_in,
        )
    if config.auth_strategy == "oauth1_tba":
        return OAuth1TBA(
            secrets,
            account_id=str(config.auth_options["account_id"]),
            consumer_key_ref=config.auth_refs["consumer_key"],
            consumer_secret_ref=config.auth_refs["consumer_secret"],
            token_id_ref=config.auth_refs["token_id"],
            token_secret_ref=config.auth_refs["token_secret"],
        )
    raise ClickException(f"Unsupported auth strategy: {config.auth_strategy!r}")


def _print_plan(
    source: str,
    project: str,
    dataset: str,
    endpoints: Sequence[Endpoint],
    *,
    sandbox: bool = False,
    guarded_free_tier: bool = False,
) -> None:
    """Render a credential-free execution plan."""
    table = Table(title=f"Dander dry run: {source}")
    table.add_column("Endpoint")
    table.add_column("Target")
    table.add_column("Mode")
    for endpoint in endpoints:
        name = endpoint.name
        if sandbox:
            mode = "REPLACE (sandbox)"
        elif guarded_free_tier:
            mode = "SCD1 (guarded billing)"
        else:
            mode = "SCD1"
        table.add_row(str(name), f"{project or '<unset>'}.{dataset}.{source}_{name}", mode)
    console.print(table)


if __name__ == "__main__":
    app()
