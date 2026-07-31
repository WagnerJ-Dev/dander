"""Dander command-line entrypoint."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from click import ClickException
from rich.console import Console
from rich.table import Table

from dander.bootstrap import (
    AdministrativeBootstrap,
    AdministrativeBootstrapError,
    DeploymentSummary,
    DeploymentVerifier,
    TerraformBootstrap,
    TerraformBootstrapError,
    write_summary,
)
from dander.catalog import (
    CatalogPublishError,
    DataplexCatalogPublisher,
    MetadataSpine,
    SemanticRegistryError,
    SemanticRegistryPublisher,
)
from dander.core.config import Settings
from dander.evidence import EvidenceBundle, EvidenceManifest, ProofEvidence, ProofStatus
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
    ApiKeyBearer,
    AuthStrategy,
    ClientCredentialPlacement,
    DefaultSecretStore,
    EnvironmentSecretStore,
    NoAuth,
    OAuth1TBA,
    OAuth2ClientCredentials,
    OAuth2JWT,
)
from dander.state import (
    BigQueryRunHistoryStore,
    BigQueryWatermarkStore,
    SqliteRunHistoryStore,
    SqliteWatermarkStore,
)
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
verify_app = typer.Typer(help="Verify deployed resources with read-only checks.")
app.add_typer(verify_app, name="verify")
console = Console()
_SOURCE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_DEFAULT_CONNECTORS_DIR = Path("connectors")
_DEFAULT_INFRA_DIR = Path("infra")
_DEFAULT_MODELS_DIR = Path("models")
_DEFAULT_CATALOG_PATH = Path(".dander/catalog.json")
_DEFAULT_BOOTSTRAP_ADMIN_DIR = Path("infra/bootstrap-admin")


@app.command()
def init(
    project: str = typer.Option(..., "--project", help="GCP project id."),
    state_bucket: str = typer.Option(
        ..., "--state-bucket", help="Existing GCS bucket for remote Terraform state."
    ),
    state_prefix: str = typer.Option(
        "dander/state", "--state-prefix", help="Object prefix for Terraform state."
    ),
    bootstrap_service_account: str = typer.Option(
        "",
        "--bootstrap-service-account",
        help="Existing dander-bootstrap service account used for platform impersonation.",
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
    runtime_publish_dataplex: bool = typer.Option(
        False,
        "--runtime-publish-dataplex",
        help="Publish catalog aspects from hosted runs; stored metadata may be billable.",
    ),
    runtime_source: str = typer.Option(
        "greenhouse_job_board",
        "--runtime-source",
        help="Connector source name passed to the hosted Cloud Run Job.",
    ),
    runtime_model: str = typer.Option(
        "stg_greenhouse__jobs",
        "--runtime-model",
        help="Transform model selected by the hosted Cloud Run Job.",
    ),
    runtime_build_models: bool = typer.Option(
        True,
        "--runtime-build-models/--runtime-no-build-models",
        help="Run hosted transform builds/tests after ingestion.",
    ),
    runtime_secret_id: str = typer.Option(
        "",
        "--runtime-secret-id",
        help="Secret Manager container exposed to the hosted connector.",
    ),
    runtime_secret_env: str = typer.Option(
        "HUBSPOT_PRIVATE_APP_TOKEN",
        "--runtime-secret-env",
        help="Environment variable carrying the hosted Secret Manager reference.",
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
    plan_path = _execute_platform_bootstrap(
        project=project,
        state_bucket=state_bucket,
        state_prefix=state_prefix,
        bootstrap_service_account=bootstrap_service_account,
        apply=apply,
        region=region,
        bigquery_location=bigquery_location,
        enable_runtime=enable_runtime,
        billing_account_id=billing_account_id,
        container_image=container_image,
        scheduler_paused=scheduler_paused,
        runtime_publish_dataplex=runtime_publish_dataplex,
        runtime_source=runtime_source,
        runtime_model=runtime_model,
        runtime_build_models=runtime_build_models,
        runtime_secret_id=runtime_secret_id,
        runtime_secret_env=runtime_secret_env,
        secret_ids=tuple(secret_ids or ()),
        github_repository=github_repository,
        github_ref=github_ref,
        enable_cost_guard=enable_cost_guard,
        cost_guard_budget_name=cost_guard_budget_name,
        cost_guard_budget_amount=cost_guard_budget_amount,
        live_cost_guard=live_cost_guard,
        infra_dir=infra_dir,
    )

    action = "applied" if apply else "planned"
    console.print(f"[green]Bootstrap {action}.[/green] Saved plan: {plan_path}")


def _execute_platform_bootstrap(
    *,
    project: str,
    state_bucket: str,
    state_prefix: str,
    bootstrap_service_account: str,
    apply: bool,
    region: str,
    bigquery_location: str,
    enable_runtime: bool,
    billing_account_id: str,
    container_image: str,
    scheduler_paused: bool,
    runtime_publish_dataplex: bool,
    runtime_source: str,
    runtime_model: str,
    runtime_build_models: bool,
    runtime_secret_id: str,
    runtime_secret_env: str,
    secret_ids: tuple[str, ...],
    github_repository: str,
    github_ref: str,
    enable_cost_guard: bool,
    cost_guard_budget_name: str,
    cost_guard_budget_amount: str,
    live_cost_guard: bool,
    infra_dir: Path,
) -> Path:
    try:
        return TerraformBootstrap(infra_dir).execute(
            project=project,
            state_bucket=state_bucket,
            state_prefix=state_prefix,
            bootstrap_service_account=bootstrap_service_account,
            apply=apply,
            region=region,
            bigquery_location=bigquery_location,
            enable_runtime=enable_runtime,
            billing_account_id=billing_account_id,
            container_image=container_image,
            scheduler_paused=scheduler_paused,
            runtime_publish_dataplex=runtime_publish_dataplex,
            runtime_source=runtime_source,
            runtime_model=runtime_model,
            runtime_build_models=runtime_build_models,
            runtime_secret_id=runtime_secret_id,
            runtime_secret_env=runtime_secret_env,
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


@app.command("init-admin-plan")
def init_admin_plan(
    project: str = typer.Option(..., "--project", help="GCP project id."),
    state_bucket: str = typer.Option(..., "--state-bucket", help="New remote-state bucket name."),
    admin_member: str = typer.Option(
        ..., "--admin-member", help="Approved user:, serviceAccount:, or group: principal."
    ),
    region: str = typer.Option("us-central1", "--region"),
    state_location: str = typer.Option("US", "--state-location"),
    bootstrap_service_account_id: str = typer.Option(
        "dander-bootstrap", "--bootstrap-service-account-id"
    ),
    billing_account_id: str = typer.Option("", "--billing-account"),
    github_repository: str = typer.Option("", "--github-repository"),
    github_ref: str = typer.Option("refs/heads/main", "--github-ref"),
    operator_artifact_dir: Path = typer.Option(  # noqa: B008
        ...,
        "--operator-artifact-dir",
        help="Secured directory outside the repository for plans and Terraform metadata.",
    ),  # noqa: B008
    infra_dir: Path = typer.Option(_DEFAULT_BOOTSTRAP_ADMIN_DIR, hidden=True),  # noqa: B008
) -> None:
    """Plan stage-zero state bucket and bootstrap identity resources."""
    try:
        plan_path = AdministrativeBootstrap(infra_dir, operator_artifact_dir).execute(
            project=project,
            state_bucket=state_bucket,
            admin_member=admin_member,
            apply=False,
            region=region,
            state_location=state_location,
            bootstrap_service_account_id=bootstrap_service_account_id,
            billing_account_id=billing_account_id,
            github_repository=github_repository,
            github_ref=github_ref,
        )
    except AdministrativeBootstrapError as error:
        raise ClickException(str(error)) from error
    console.print(f"[green]Administrative bootstrap planned.[/green] Saved plan: {plan_path}")


@app.command("init-admin-apply")
def init_admin_apply(
    project: str = typer.Option(..., "--project", help="GCP project id."),
    state_bucket: str = typer.Option(..., "--state-bucket", help="New remote-state bucket name."),
    admin_member: str = typer.Option(
        ..., "--admin-member", help="Approved user:, serviceAccount:, or group: principal."
    ),
    region: str = typer.Option("us-central1", "--region"),
    state_location: str = typer.Option("US", "--state-location"),
    bootstrap_service_account_id: str = typer.Option(
        "dander-bootstrap", "--bootstrap-service-account-id"
    ),
    billing_account_id: str = typer.Option("", "--billing-account"),
    github_repository: str = typer.Option("", "--github-repository"),
    github_ref: str = typer.Option("refs/heads/main", "--github-ref"),
    operator_artifact_dir: Path = typer.Option(  # noqa: B008
        ...,
        "--operator-artifact-dir",
        help="Secured directory outside the repository for plans and Terraform metadata.",
    ),  # noqa: B008
    infra_dir: Path = typer.Option(_DEFAULT_BOOTSTRAP_ADMIN_DIR, hidden=True),  # noqa: B008
) -> None:
    """Apply the reviewed stage-zero plan after explicit confirmation."""
    if not typer.confirm(
        f"Apply administrative bootstrap to GCP project {project!r}?", default=False
    ):
        raise typer.Abort()
    try:
        plan_path = AdministrativeBootstrap(infra_dir, operator_artifact_dir).execute(
            project=project,
            state_bucket=state_bucket,
            admin_member=admin_member,
            apply=True,
            region=region,
            state_location=state_location,
            bootstrap_service_account_id=bootstrap_service_account_id,
            billing_account_id=billing_account_id,
            github_repository=github_repository,
            github_ref=github_ref,
        )
    except AdministrativeBootstrapError as error:
        raise ClickException(str(error)) from error
    console.print(f"[green]Administrative bootstrap applied.[/green] Saved plan: {plan_path}")


@app.command("init-platform-plan")
def init_platform_plan(
    project: str = typer.Option(..., "--project", help="GCP project id."),
    state_bucket: str = typer.Option(..., "--state-bucket", help="Existing remote-state bucket."),
    bootstrap_service_account: str = typer.Option(..., "--bootstrap-service-account"),
    state_prefix: str = typer.Option("dander/state", "--state-prefix"),
    region: str = typer.Option("us-central1", "--region"),
    bigquery_location: str = typer.Option("US", "--bigquery-location"),
    infra_dir: Path = typer.Option(_DEFAULT_INFRA_DIR, hidden=True),  # noqa: B008
) -> None:
    """Plan platform Terraform while impersonating the stage-zero identity."""
    plan_path = _execute_platform_bootstrap(
        project=project,
        state_bucket=state_bucket,
        state_prefix=state_prefix,
        bootstrap_service_account=bootstrap_service_account,
        apply=False,
        region=region,
        bigquery_location=bigquery_location,
        enable_runtime=False,
        billing_account_id="",
        container_image="",
        scheduler_paused=True,
        runtime_publish_dataplex=False,
        runtime_source="greenhouse_job_board",
        runtime_model="stg_greenhouse__jobs",
        runtime_build_models=True,
        runtime_secret_id="",
        runtime_secret_env="HUBSPOT_PRIVATE_APP_TOKEN",
        secret_ids=(),
        github_repository="",
        github_ref="refs/heads/main",
        enable_cost_guard=False,
        cost_guard_budget_name="dander-sbx-cap",
        cost_guard_budget_amount="5.00",
        live_cost_guard=False,
        infra_dir=infra_dir,
    )
    console.print(f"[green]Platform bootstrap planned.[/green] Saved plan: {plan_path}")


@app.command("init-platform-apply")
def init_platform_apply(
    project: str = typer.Option(..., "--project", help="GCP project id."),
    state_bucket: str = typer.Option(..., "--state-bucket", help="Existing remote-state bucket."),
    bootstrap_service_account: str = typer.Option(..., "--bootstrap-service-account"),
    state_prefix: str = typer.Option("dander/state", "--state-prefix"),
    region: str = typer.Option("us-central1", "--region"),
    bigquery_location: str = typer.Option("US", "--bigquery-location"),
    infra_dir: Path = typer.Option(_DEFAULT_INFRA_DIR, hidden=True),  # noqa: B008
) -> None:
    """Apply the reviewed platform plan through the bootstrap identity."""
    if not typer.confirm(f"Apply platform bootstrap to GCP project {project!r}?", default=False):
        raise typer.Abort()
    try:
        plan_path = TerraformBootstrap(infra_dir).apply_saved_plan(
            project=project,
            state_bucket=state_bucket,
            state_prefix=state_prefix,
            bootstrap_service_account=bootstrap_service_account,
        )
    except TerraformBootstrapError as error:
        raise ClickException(str(error)) from error
    console.print(f"[green]Platform bootstrap applied.[/green] Saved plan: {plan_path}")


@verify_app.command("deployment")
def verify_deployment(
    project: str = typer.Option(..., "--project", help="GCP project id to inspect."),
    json_output: Path = typer.Option(  # noqa: B008
        Path("evidence/bootstrap-summary.json"),
        "--json",
        help="Write the sanitized verification summary to this path.",
    ),  # noqa: B008
    evidence_dir: Path | None = typer.Option(  # noqa: B008
        None,
        "--evidence-dir",
        help="Also write the complete sanitized evidence bundle to this directory.",
    ),
    state_bucket: str = typer.Option(
        ...,
        "--state-bucket",
        help="Expected remote-state bucket initialized by stage zero.",
    ),
    state_prefix: str = typer.Option(
        ...,
        "--state-prefix",
        help="Expected remote-state prefix initialized by stage zero.",
    ),
    dataset: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--dataset",
        help="Dataset to verify; repeat for multiple datasets (defaults to raw, staging, marts).",
    ),
    runtime_job: str | None = typer.Option(
        None,
        "--runtime-job",
        help="Cloud Run Job name to verify, for example dander-greenhouse-public.",
    ),
    scheduler_job: str | None = typer.Option(
        None,
        "--scheduler-job",
        help="Cloud Scheduler job name to verify.",
    ),
    runtime_service_account: str | None = typer.Option(
        None,
        "--runtime-service-account",
        help=(
            "Expected runtime service account email; inferred from the Cloud Run Job when omitted."
        ),
    ),
    runtime_image: str | None = typer.Option(
        None,
        "--runtime-image",
        help="Expected immutable runtime image digest.",
    ),
    secret_id: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--secret-id",
        help="Secret Manager container to verify; repeat for multiple secrets.",
    ),
    region: str = typer.Option("us-central1", "--region", help="Cloud Run/Scheduler region."),
    expect_cost_guard: bool = typer.Option(
        False,
        "--expect-cost-guard",
        help="Also verify the named budget, notification topic, function, and billing linkage.",
    ),
    billing_account_id: str | None = typer.Option(
        None,
        "--billing-account",
        help="Billing account id used by --expect-cost-guard.",
    ),
    cost_guard_budget_name: str = typer.Option("dander-sbx-cap", "--cost-guard-budget-name"),
    cost_guard_amount: float = typer.Option(5.0, "--cost-guard-amount"),
    cost_guard_topic: str = typer.Option("dander-stop-billing", "--cost-guard-topic"),
    cost_guard_function: str = typer.Option("dander-stop-billing", "--cost-guard-function"),
    cost_guard_simulate: bool = typer.Option(
        True,
        "--cost-guard-simulate/--cost-guard-live",
        help="Expect simulation mode for the cost guard (the safe default).",
    ),
    publish_dataplex: bool = typer.Option(
        False,
        "--publish-dataplex",
        help="Expect the runtime to have the narrow Dataplex catalog role.",
    ),
    infra_dir: Path = typer.Option(_DEFAULT_INFRA_DIR, hidden=True),  # noqa: B008
) -> None:
    """Verify the bootstrap's actual resources and save sanitized evidence."""
    summary = DeploymentVerifier(project=project, infra_dir=infra_dir).verify(
        datasets=tuple(dataset or ("raw", "staging", "marts")),
        state_bucket=state_bucket,
        state_prefix=state_prefix,
        runtime_job=runtime_job,
        scheduler_job=scheduler_job,
        runtime_service_account=runtime_service_account,
        runtime_image=runtime_image,
        secret_ids=tuple(secret_id or ()),
        region=region,
        expect_cost_guard=expect_cost_guard,
        billing_account_id=billing_account_id,
        cost_guard_budget_name=cost_guard_budget_name,
        cost_guard_amount=cost_guard_amount,
        cost_guard_topic=cost_guard_topic,
        cost_guard_function=cost_guard_function,
        cost_guard_simulate=cost_guard_simulate,
        publish_dataplex=publish_dataplex,
    )
    write_summary(summary, json_output)
    if evidence_dir is not None:
        _write_bootstrap_evidence(summary, evidence_dir)
    table = Table(title=f"Dander deployment verification: {project}")
    table.add_column("Check")
    table.add_column("Result")
    table.add_column("Detail")
    for check in summary.checks:
        table.add_row(check.name, "PASS" if check.ok else "FAIL", check.detail)
    console.print(table)
    console.print(f"Evidence: {json_output}")
    if not summary.passed:
        raise ClickException("Deployment verification failed; inspect the evidence summary.")


def _write_bootstrap_evidence(summary: DeploymentSummary, evidence_dir: Path) -> None:
    """Adapt deployment checks into the standard evidence bundle without copying payloads."""
    checks = summary.checks
    passed = summary.passed
    proof = ProofEvidence(
        status=ProofStatus.PASSED if passed else ProofStatus.FAILED,
        started_at_utc=os.environ.get("DANDER_PROOF_STARTED_AT_UTC", summary.checked_at_utc),
        ended_at_utc=summary.checked_at_utc,
        operation="deployment verification",
        resource_ids=tuple(check.name for check in checks),
        row_counts={"checks": len(checks)},
        failure_reason=None if passed else "one or more deployment checks failed",
    )
    cost_checks = tuple(check for check in checks if check.name.startswith("cost_guard"))
    proofs: dict[str, ProofEvidence] = {"bootstrap": proof}
    if cost_checks:
        cost_passed = all(check.ok for check in cost_checks)
        proofs["cost-guard"] = ProofEvidence(
            status=ProofStatus.PASSED if cost_passed else ProofStatus.FAILED,
            started_at_utc=proof.started_at_utc,
            ended_at_utc=proof.ended_at_utc,
            operation="cost-guard resource verification",
            resource_ids=tuple(check.name for check in cost_checks),
            row_counts={"checks": len(cost_checks)},
            failure_reason=None if cost_passed else "one or more cost-guard checks failed",
        )
    manifest = EvidenceManifest(
        commit_sha=os.environ.get("GITHUB_SHA", "local"),
        workflow_run_id=os.environ.get("GITHUB_RUN_ID", "local"),
        checked_at_utc=summary.checked_at_utc,
        gcp_project_alias=os.environ.get("DANDER_GCP_PROJECT_ALIAS", summary.project_id),
        container_digest=os.environ.get("DANDER_CONTAINER_DIGEST", "unknown"),
        terraform_plan_sha256=os.environ.get("DANDER_TERRAFORM_PLAN_SHA256", "unknown"),
        proofs=proofs,
    )
    EvidenceBundle(evidence_dir).write(manifest)


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
    build_models: bool = typer.Option(
        False,
        "--build-models",
        help="Build all transform models and tests after successful ingestion.",
    ),
    models_dir: Path = typer.Option(_DEFAULT_MODELS_DIR, "--models-dir"),  # noqa: B008
    selected_models: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--select-model",
        help="Build/catalog one model root and its dependencies. Repeat for multiple roots.",
    ),
    catalog_output: Path | None = typer.Option(  # noqa: B008
        None,
        "--catalog-output",
        help="Write the semantic registry after transforms complete.",
    ),
    publish_dataplex: bool = typer.Option(
        False,
        "--publish-dataplex",
        help="Publish generated aspects after transforms; may incur metadata storage charges.",
    ),
    dataplex_location: str = typer.Option("us", "--dataplex-location"),
) -> None:
    """Run ingestion, then optionally build transforms and publish the metadata spine."""
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
        history=(
            SqliteRunHistoryStore(state_path)
            if sandbox
            else BigQueryRunHistoryStore(
                project=resolved_project,
                dataset=resolved_dataset,
            )
        ),
    ).run()

    _run_post_ingestion(
        project=resolved_project,
        models_dir=models_dir,
        selected_models=selected_models,
        build_models=build_models,
        catalog_output=catalog_output,
        publish_dataplex=publish_dataplex,
        dataplex_location=dataplex_location,
    )

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


def _run_post_ingestion(
    *,
    project: str,
    models_dir: Path,
    selected_models: Sequence[str] | None,
    build_models: bool,
    catalog_output: Path | None,
    publish_dataplex: bool,
    dataplex_location: str,
) -> None:
    """Execute the hosted transform/catalog tail only after ingestion commits."""
    try:
        if build_models:
            BigQueryTransformRunner(project=project).build(
                models_dir,
                selected=selected_models,
            )
        if catalog_output is None and not publish_dataplex:
            return
        transform_project = TransformProject.load(models_dir, project_id=project)
        assets = MetadataSpine().compile(transform_project, selected=selected_models)
        manifest = MetadataSpine().manifest(assets)
        if catalog_output is not None:
            SemanticRegistryPublisher().publish(manifest, catalog_output)
        if publish_dataplex:
            publisher = DataplexCatalogPublisher(
                project=project,
                location=dataplex_location,
            )
            for asset in assets:
                publisher.publish(asset)
    except (
        CatalogPublishError,
        SemanticRegistryError,
        TransformProjectError,
        TransformRunError,
    ) as error:
        raise ClickException(str(error)) from error


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
    if config.auth_strategy == "api_key_bearer":
        if config.auth_ref is None:
            raise ClickException("api_key_bearer connector is missing auth_ref")
        return ApiKeyBearer(secrets, config.auth_ref)
    if config.auth_strategy == "oauth2_client_credentials":
        token_url = config.auth_options["token_url"]
        subject = config.auth_options.get("subject")
        credential_placement = config.auth_options.get("credential_placement", "basic")
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
            credential_placement=ClientCredentialPlacement(str(credential_placement)),
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
