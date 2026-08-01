"""End-to-end execution for one project-defined Dander pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

from dander.catalog import MetadataSpine, SemanticRegistryPublisher
from dander.state import RunStage, RunStatus
from dander.transform import TransformProject, TransformRunResult

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from dander.catalog import CatalogAsset, MetadataStore
    from dander.ingestion import SourceConfig
    from dander.runtime import PipelineRunner, PipelineRunResult
    from dander.state import RunHistoryStore

_LOGGER = logging.getLogger(__name__)


class _TransformRunner(Protocol):
    def build(
        self,
        models_dir: Path,
        *,
        selected: Iterable[str] | None = None,
    ) -> TransformRunResult:
        """Build models and run their assertions."""


class _DataplexPublisher(Protocol):
    def publish(self, asset: CatalogAsset) -> str:
        """Project one canonical asset into Dataplex."""


@dataclass(frozen=True)
class PipelineExecutionResult:
    """Non-sensitive summary for the complete Dander pipeline lifecycle."""

    run_id: str
    pipeline_id: str
    ingestion: PipelineRunResult
    models: tuple[str, ...]
    assertions: int
    assets: int


class PipelineExecutor:
    """Own ingestion, transforms/tests, metadata publication, and lifecycle state."""

    def __init__(
        self,
        *,
        pipeline_id: str,
        source_config: SourceConfig,
        ingestion: PipelineRunner,
        history: RunHistoryStore,
        project: str,
        models_dir: Path,
        selected_models: Iterable[str] | None,
        build_models: bool,
        transform_runner: _TransformRunner | None = None,
        metadata_store: MetadataStore | None = None,
        registry_output: Path | None = None,
        dataplex_publisher: _DataplexPublisher | None = None,
    ) -> None:
        if build_models and transform_runner is None:
            raise ValueError("A transform runner is required when build_models is enabled")
        self._pipeline_id = pipeline_id
        self._source_config = source_config
        self._ingestion = ingestion
        self._history = history
        self._project = project
        self._models_dir = models_dir
        self._selected_models = tuple(selected_models) if selected_models is not None else None
        self._build_models = build_models
        self._transform_runner = transform_runner
        self._metadata_store = metadata_store
        self._registry_output = registry_output
        self._dataplex_publisher = dataplex_publisher

    def execute(self) -> PipelineExecutionResult:
        """Execute every enabled stage and record one truthful terminal outcome."""
        run_id = uuid4().hex
        stage = RunStage.INGEST
        endpoints = extracted = affected = models = assertions = assets = 0
        self._history.start(
            run_id,
            self._source_config.name,
            pipeline_id=self._pipeline_id,
        )
        try:
            ingestion_result = self._ingestion.run(run_id=run_id)
            endpoints = len(ingestion_result.endpoints)
            extracted = sum(result.extracted for result in ingestion_result.endpoints)
            affected = sum(result.affected for result in ingestion_result.endpoints)

            transform_result = TransformRunResult(models=(), assertions=0)
            if self._build_models:
                stage = RunStage.TRANSFORM
                self._checkpoint(
                    run_id,
                    stage,
                    endpoints=endpoints,
                    extracted=extracted,
                    affected=affected,
                )
                assert self._transform_runner is not None
                transform_result = self._transform_runner.build(
                    self._models_dir,
                    selected=self._selected_models,
                )
                models = len(transform_result.models)
                assertions = transform_result.assertions

            compiled_assets: tuple[CatalogAsset, ...] = ()
            if self._publishes_metadata:
                stage = RunStage.METADATA
                self._checkpoint(
                    run_id,
                    stage,
                    endpoints=endpoints,
                    extracted=extracted,
                    affected=affected,
                    models=models,
                    assertions=assertions,
                )
                transform_project = TransformProject.load(
                    self._models_dir,
                    project_id=self._project,
                )
                spine = MetadataSpine()
                compiled_assets = spine.compile(
                    transform_project,
                    selected=self._selected_models,
                )
                manifest = spine.pipeline_manifest(
                    pipeline_id=self._pipeline_id,
                    source=self._source_config,
                    assets=compiled_assets,
                )
                assets = len(compiled_assets)
                if self._metadata_store is not None:
                    self._metadata_store.publish(
                        pipeline_id=self._pipeline_id,
                        run_id=run_id,
                        manifest=manifest,
                    )
                if self._registry_output is not None:
                    SemanticRegistryPublisher().publish(manifest, self._registry_output)
                if self._dataplex_publisher is not None:
                    for asset in compiled_assets:
                        self._dataplex_publisher.publish(asset)

            self._history.finish(
                run_id,
                RunStatus.SUCCEEDED,
                endpoints=endpoints,
                extracted=extracted,
                affected=affected,
                models=models,
                assertions=assertions,
                assets=assets,
            )
        except Exception:
            try:
                self._history.finish(
                    run_id,
                    RunStatus.FAILED,
                    endpoints=endpoints,
                    extracted=extracted,
                    affected=affected,
                    models=models,
                    assertions=assertions,
                    assets=assets,
                    failure_stage=stage,
                )
            except Exception:
                _LOGGER.exception(
                    "run_history_finish_failed",
                    extra={
                        "dander_event": "run_history_finish_failed",
                        "pipeline_id": self._pipeline_id,
                        "run_id": run_id,
                    },
                )
            raise
        return PipelineExecutionResult(
            run_id=run_id,
            pipeline_id=self._pipeline_id,
            ingestion=ingestion_result,
            models=transform_result.models,
            assertions=transform_result.assertions,
            assets=len(compiled_assets),
        )

    @property
    def _publishes_metadata(self) -> bool:
        return any(
            value is not None
            for value in (
                self._metadata_store,
                self._registry_output,
                self._dataplex_publisher,
            )
        )

    def _checkpoint(
        self,
        run_id: str,
        stage: RunStage,
        *,
        endpoints: int,
        extracted: int,
        affected: int,
        models: int = 0,
        assertions: int = 0,
    ) -> None:
        self._history.checkpoint(
            run_id,
            stage,
            endpoints=endpoints,
            extracted=extracted,
            affected=affected,
            models=models,
            assertions=assertions,
        )
