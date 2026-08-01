"""Create an all-paused Dander manifest for an approval-gated live proof."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from dander.project import load_project_config


def prepare_config(
    source: Path,
    output: Path,
    *,
    publish_dataplex_pipeline: str | None = None,
) -> None:
    """Copy a project manifest with every schedule paused and optional Dataplex scoped."""
    source = source.resolve()
    output = output.resolve()
    if source == output:
        raise ValueError("Live-proof output must not overwrite the tracked project manifest")
    if source.parent != output.parent:
        raise ValueError("Live-proof output must stay beside the tracked project manifest")
    if output.is_symlink():
        raise ValueError("Live-proof output must not be a symlink")

    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("pipelines"), dict):
        raise ValueError("Dander project manifest must contain a pipelines mapping")
    pipelines = raw["pipelines"]
    if publish_dataplex_pipeline is not None and publish_dataplex_pipeline not in pipelines:
        raise ValueError("Dataplex proof pipeline is not declared in the project manifest")
    for pipeline_id, pipeline in pipelines.items():
        if not isinstance(pipeline, dict):
            raise ValueError(f"Pipeline {pipeline_id!r} must be a mapping")
        pipeline["paused"] = True
        pipeline["build_models"] = True
        pipeline["publish_dataplex"] = pipeline_id == publish_dataplex_pipeline

    output.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    manifest = load_project_config(output)
    manifest.validate_references(output.parent)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("dander.yaml"))
    parser.add_argument("--output", type=Path, default=Path("dander.live-proof.yaml"))
    parser.add_argument("--publish-dataplex-pipeline")
    args = parser.parse_args()
    prepare_config(
        args.input,
        args.output,
        publish_dataplex_pipeline=args.publish_dataplex_pipeline,
    )


if __name__ == "__main__":
    main()
