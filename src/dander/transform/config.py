"""Typed YAML boundary models for transform metadata."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from dander.transform.model import Materialization

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
type Scalar = str | int | float | bool

if TYPE_CHECKING:
    from pathlib import Path


class TransformConfigError(ValueError):
    """Raised when model metadata is missing, unsafe, or internally inconsistent."""


class ColumnMetadata(BaseModel):
    """Catalog and warehouse metadata for one model column."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(pattern=_IDENTIFIER.pattern)
    data_type: str = Field(alias="type", min_length=1)
    description: str = Field(min_length=1)


class RelationshipMetadata(BaseModel):
    """Target relation and field for a referential-integrity assertion."""

    model_config = ConfigDict(extra="forbid")

    to: str = Field(pattern=_IDENTIFIER.pattern)
    field: str = Field(pattern=_IDENTIFIER.pattern)


class GenericTestMetadata(BaseModel):
    """Declarative generic tests applied to one model column."""

    model_config = ConfigDict(extra="forbid")

    column: str = Field(pattern=_IDENTIFIER.pattern)
    not_null: bool = False
    unique: bool = False
    accepted_values: list[Scalar] | None = None
    relationships: RelationshipMetadata | None = None

    @model_validator(mode="after")
    def require_assertion(self) -> GenericTestMetadata:
        """Reject empty test declarations and empty accepted-value sets."""
        if self.accepted_values == []:
            raise ValueError("accepted_values must contain at least one value")
        if not (
            self.not_null
            or self.unique
            or self.accepted_values is not None
            or self.relationships is not None
        ):
            raise ValueError("a generic test must enable at least one assertion")
        return self


class ModelMetadata(BaseModel):
    """Validated metadata spine for a SQL model."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(pattern=_IDENTIFIER.pattern)
    description: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    materialization: Materialization = Materialization.VIEW
    dataset: str = Field(default="staging", pattern=_IDENTIFIER.pattern)
    source_system: str = Field(min_length=1)
    sensitivity: str = Field(min_length=1)
    columns: list[ColumnMetadata] = Field(min_length=1)
    tests: list[GenericTestMetadata] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_columns_and_tests(self) -> ModelMetadata:
        """Require unique columns and test references that resolve within the model."""
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("model column names must be unique")
        declared = set(names)
        if unknown := sorted({test.column for test in self.tests} - declared):
            raise ValueError(f"tests reference undeclared columns: {', '.join(unknown)}")
        return self


def load_model_metadata(path: Path) -> ModelMetadata:
    """Load one model sidecar without reflecting authored values into errors.

    Args:
        path: YAML sidecar to load.

    Returns:
        Validated model metadata.

    Raises:
        TransformConfigError: If the file cannot be read or fails schema validation.
    """
    try:
        raw = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as error:
        raise TransformConfigError(f"Cannot read model metadata: {path}") from error
    if not isinstance(raw, dict):
        raise TransformConfigError(f"Model metadata must be a mapping: {path}")
    try:
        return ModelMetadata.model_validate(raw)
    except ValidationError as error:
        locations = sorted(
            {".".join(str(part) for part in issue["loc"]) or "<root>" for issue in error.errors()}
        )
        raise TransformConfigError(
            f"Invalid model metadata at {path}; check: {', '.join(locations)}"
        ) from error
