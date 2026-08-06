"""CLI coverage for the durable metadata spine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from dander.catalog import SqliteMetadataStore
from dander.cli.main import app
from dander.state import RunStage, RunStatus, SqliteRunHistoryStore

if TYPE_CHECKING:
    from pathlib import Path


def _seed(path: Path) -> None:
    SqliteMetadataStore(path).publish(
        pipeline_id="greenhouse_jobs",
        run_id="run-1",
        manifest={
            "schema_version": 2,
            "pipeline_id": "greenhouse_jobs",
            "source": {"name": "greenhouse_job_board", "endpoints": []},
            "assets": [
                {
                    "name": "stg_greenhouse__jobs",
                    "relation": "example.staging.stg_greenhouse__jobs",
                    "upstream_relations": ["example.raw.greenhouse_job_board_jobs"],
                    "metrics": [
                        {
                            "name": "published_job_count",
                            "description": "Distinct public jobs.",
                            "calculation": "COUNT(DISTINCT `job_id`)",
                        }
                    ],
                }
            ],
        },
    )
    history = SqliteRunHistoryStore(path)
    history.start("run-1", "greenhouse_job_board", pipeline_id="greenhouse_jobs")
    history.finish(
        "run-1",
        RunStatus.SUCCEEDED,
        endpoints=1,
        extracted=25,
        affected=25,
        models=1,
        assertions=2,
        assets=1,
    )


def test_metadata_commands_read_the_local_spine(tmp_path: Path) -> None:
    state = tmp_path / "state.db"
    _seed(state)
    runner = CliRunner()

    listed = runner.invoke(app, ["metadata", "list", "--local", "--state-path", str(state)])
    metrics = runner.invoke(app, ["metadata", "metrics", "--local", "--state-path", str(state)])
    lineage = runner.invoke(
        app,
        [
            "metadata",
            "lineage",
            "stg_greenhouse__jobs",
            "--local",
            "--state-path",
            str(state),
        ],
    )
    runs = runner.invoke(app, ["metadata", "runs", "--local", "--state-path", str(state)])

    assert listed.exit_code == 0 and "greenhouse_job_board" in listed.stdout
    assert "stg_greenhouse__jobs" in listed.stdout
    assert metrics.exit_code == 0 and "published_job" in metrics.stdout
    assert "COUNT(DISTINCT" in metrics.stdout and "job_id" in metrics.stdout
    assert lineage.exit_code == 0 and "greenhouse_job_board_jobs" in lineage.stdout
    assert runs.exit_code == 0 and "succeeded" in runs.stdout


def test_metadata_show_returns_governed_metric_definition(tmp_path: Path) -> None:
    state = tmp_path / "state.db"
    _seed(state)

    result = CliRunner().invoke(
        app,
        [
            "metadata",
            "show",
            "published_job_count",
            "--local",
            "--state-path",
            str(state),
        ],
    )

    assert result.exit_code == 0
    assert '"kind": "metric"' in result.stdout
    assert "Distinct public jobs." in result.stdout


def test_metadata_runs_renders_active_run(tmp_path: Path) -> None:
    state = tmp_path / "state.db"
    history = SqliteRunHistoryStore(state)
    history.start("run-active", "greenhouse_job_board", pipeline_id="greenhouse_jobs")

    result = CliRunner().invoke(
        app,
        ["metadata", "runs", "--local", "--state-path", str(state)],
    )

    assert result.exit_code == 0
    assert "running" in result.stdout


def test_metadata_runs_renders_safe_failure_summary(tmp_path: Path) -> None:
    state = tmp_path / "state.db"
    history = SqliteRunHistoryStore(state)
    history.start("run-failed", "salesforce", pipeline_id="salesforce_crm")
    history.finish(
        "run-failed",
        RunStatus.FAILED,
        endpoints=0,
        extracted=0,
        affected=0,
        failure_stage=RunStage.INGEST,
        failure_code="authentication_failed",
        failure_summary="Authentication failed. Verify the configured secret.",
    )

    result = CliRunner().invoke(
        app,
        ["metadata", "runs", "--local", "--state-path", str(state)],
    )

    assert result.exit_code == 0
    assert "authentication" in result.stdout
    assert "configured" in result.stdout
