"""BigQuery materialization and generic data-test execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

import sqlglot
from google.cloud import bigquery

from dander.transform.model import Materialization
from dander.transform.project import TransformModel, TransformProject, TransformProjectError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from dander.transform.config import GenericTestMetadata


class TransformRunError(RuntimeError):
    """Raised when model execution or a generic assertion fails."""


class _QueryRow(Protocol):
    def __getitem__(self, key: str) -> object:
        """Return a projected result value by column name."""


class _QueryJob(Protocol):
    def result(self) -> Iterable[_QueryRow]:
        """Wait for completion and return query rows."""


class _BigQueryClient(Protocol):
    def query(self, query: str) -> _QueryJob:
        """Submit BigQuery Standard SQL."""


@dataclass(frozen=True)
class TransformRunResult:
    """Summary of models materialized and assertions evaluated."""

    models: tuple[str, ...]
    assertions: int


@dataclass(frozen=True)
class _Assertion:
    name: str
    sql: str


class BigQueryTransformRunner:
    """Build and test selected transform models with an injected BigQuery client."""

    def __init__(self, *, project: str, client: _BigQueryClient | None = None) -> None:
        self._project = project
        self._client = client or cast("_BigQueryClient", bigquery.Client(project=project))

    def build(
        self,
        models_dir: Path,
        *,
        selected: Iterable[str] | None = None,
    ) -> TransformRunResult:
        """Materialize selected models in dependency order, then run their assertions."""
        project = TransformProject.load(models_dir, project_id=self._project)
        models = project.ordered(selected)
        compiled = [(model, project.compile(model)) for model in models]
        statements = [_materialization_sql(project, model, query) for model, query in compiled]
        assertions = [
            assertion for model in models for assertion in _compile_assertions(project, model)
        ]
        for statement in statements:
            self._client.query(statement).result()
        self._run_assertions(assertions)
        return TransformRunResult(
            models=tuple(model.name for model in models),
            assertions=len(assertions),
        )

    def test(
        self,
        models_dir: Path,
        *,
        selected: Iterable[str] | None = None,
    ) -> TransformRunResult:
        """Run assertions against already-materialized selected model relations."""
        project = TransformProject.load(models_dir, project_id=self._project)
        models = project.ordered(selected)
        assertions = [
            assertion for model in models for assertion in _compile_assertions(project, model)
        ]
        self._run_assertions(assertions)
        return TransformRunResult(
            models=tuple(model.name for model in models),
            assertions=len(assertions),
        )

    def _run_assertions(self, assertions: Iterable[_Assertion]) -> None:
        failures: list[str] = []
        for assertion in assertions:
            rows = list(self._client.query(assertion.sql).result())
            if len(rows) != 1:
                raise TransformRunError(f"Assertion returned an invalid result: {assertion.name}")
            try:
                raw_count = rows[0]["failures"]
            except (KeyError, TypeError, ValueError) as error:
                raise TransformRunError(
                    f"Assertion returned an invalid result: {assertion.name}"
                ) from error
            if isinstance(raw_count, bool) or not isinstance(raw_count, (int, str)):
                raise TransformRunError(f"Assertion returned an invalid result: {assertion.name}")
            try:
                failure_count = int(raw_count)
            except ValueError as error:
                raise TransformRunError(
                    f"Assertion returned an invalid result: {assertion.name}"
                ) from error
            if failure_count > 0:
                failures.append(assertion.name)
        if failures:
            raise TransformRunError(f"Data tests failed: {', '.join(failures)}")


def _materialization_sql(project: TransformProject, model: TransformModel, query: str) -> str:
    relation = project.relation_for_model(model)
    match model.metadata.materialization:
        case Materialization.VIEW:
            return f"CREATE OR REPLACE VIEW {relation} AS\n{query}"
        case Materialization.TABLE:
            return f"CREATE OR REPLACE TABLE {relation} AS\n{query}"
        case Materialization.INCREMENTAL:
            raise TransformProjectError(
                f"Incremental materialization is not implemented for model {model.name}"
            )


def _compile_assertions(
    project: TransformProject,
    model: TransformModel,
) -> tuple[_Assertion, ...]:
    relation = project.relation_for_model(model)
    assertions: list[_Assertion] = []
    for test in model.metadata.tests:
        assertions.extend(_assertions_for_test(project, model.name, relation, test))
    return tuple(assertions)


def _assertions_for_test(
    project: TransformProject,
    model_name: str,
    relation: str,
    test: GenericTestMetadata,
) -> list[_Assertion]:
    column = f"`{test.column}`"
    assertions: list[_Assertion] = []
    if test.not_null:
        assertions.append(
            _Assertion(
                name=f"{model_name}.{test.column}.not_null",
                sql=f"SELECT COUNTIF({column} IS NULL) AS failures FROM {relation}",
            )
        )
    if test.unique:
        assertions.append(
            _Assertion(
                name=f"{model_name}.{test.column}.unique",
                sql=(
                    "SELECT COUNT(*) AS failures FROM (\n"
                    f"  SELECT {column}\n"
                    f"  FROM {relation}\n"
                    f"  WHERE {column} IS NOT NULL\n"
                    f"  GROUP BY {column}\n"
                    "  HAVING COUNT(*) > 1\n"
                    ")"
                ),
            )
        )
    if test.accepted_values is not None:
        rendered = ", ".join(
            sqlglot.exp.convert(value).sql(dialect="bigquery") for value in test.accepted_values
        )
        assertions.append(
            _Assertion(
                name=f"{model_name}.{test.column}.accepted_values",
                sql=(
                    f"SELECT COUNTIF({column} IS NOT NULL AND {column} NOT IN ({rendered})) "
                    f"AS failures FROM {relation}"
                ),
            )
        )
    if test.relationships is not None:
        if test.relationships.to in project.models:
            parent_model = project.models[test.relationships.to]
            parent_columns = {column.name for column in parent_model.metadata.columns}
            if test.relationships.field not in parent_columns:
                raise TransformProjectError(
                    "Relationship test references an undeclared parent column: "
                    f"{test.relationships.to}.{test.relationships.field}"
                )
        parent = project.relation_for_ref(test.relationships.to)
        parent_field = f"`{test.relationships.field}`"
        assertions.append(
            _Assertion(
                name=f"{model_name}.{test.column}.relationships",
                sql=(
                    "SELECT COUNT(*) AS failures\n"
                    f"FROM {relation} AS child\n"
                    f"LEFT JOIN {parent} AS parent\n"
                    f"  ON child.{column} = parent.{parent_field}\n"
                    f"WHERE child.{column} IS NOT NULL AND parent.{parent_field} IS NULL"
                ),
            )
        )
    return assertions
