"""BigQuery cursor compare-and-set and lease-fencing contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dander.concurrency import FencingToken
from dander.state import BigQueryWatermarkStore

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from google.cloud import bigquery


class _Job:
    def __init__(
        self,
        *,
        affected: int | None = None,
        rows: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        self.num_dml_affected_rows = affected
        self._rows = list(rows)

    def result(self) -> list[Mapping[str, Any]]:
        return self._rows


class _Client:
    def __init__(self, *, affected: int = 1) -> None:
        self.affected = affected
        self.queries: list[str] = []
        self.configs: list[bigquery.QueryJobConfig | None] = []

    def query(
        self,
        query: str,
        *,
        job_config: bigquery.QueryJobConfig | None = None,
    ) -> _Job:
        self.queries.append(query)
        self.configs.append(job_config)
        return _Job(affected=self.affected)


def test_bigquery_compare_and_set_matches_expected_cursor_atomically() -> None:
    client = _Client(affected=1)
    store = BigQueryWatermarkStore(
        project="unit-project",
        dataset="raw",
        client=client,
    )

    assert store.compare_and_set(
        "hubspot",
        "companies",
        expected="before",
        cursor="after",
    )

    merge = client.queries[-1]
    assert "target.last_cursor IS NOT DISTINCT FROM @expected" in merge
    assert "WHEN NOT MATCHED AND @expected IS NULL" in merge


def test_bigquery_compare_and_set_reports_stale_cursor_without_fence() -> None:
    store = BigQueryWatermarkStore(
        project="unit-project",
        dataset="raw",
        client=_Client(affected=0),
    )

    assert not store.compare_and_set(
        "hubspot",
        "companies",
        expected="stale",
        cursor="after",
    )


def test_bigquery_cursor_commit_dml_touches_matching_lease_in_same_transaction() -> None:
    client = _Client()
    store = BigQueryWatermarkStore(
        project="unit-project",
        dataset="raw",
        client=client,
    )
    fence = FencingToken(
        lease_table="unit-project.meta._dander_leases",
        pipeline_id="hubspot_companies",
        run_id="run-one",
        token=9,
    )

    assert store.compare_and_set(
        "hubspot",
        "companies",
        expected="before",
        cursor="after",
        fence=fence,
    )

    script = client.queries[-1]
    assert script.startswith("BEGIN TRANSACTION;\nUPDATE `unit-project.meta._dander_leases`")
    assert "pipeline_id = @dander_pipeline_id" in script
    assert "run_id = @dander_run_id" in script
    assert "fencing_token = @dander_fencing_token" in script
    assert "ASSERT @@row_count = 1 AS 'Dander pipeline lease lost'" in script
    assert "MERGE `unit-project.raw._dander_watermarks`" in script
    assert "ASSERT @@row_count = 1 AS 'Dander watermark boundary changed'" in script
    assert script.index("UPDATE `unit-project.meta._dander_leases`") < script.index(
        "MERGE `unit-project.raw._dander_watermarks`"
    )
    assert "SELECT" not in script.split("ASSERT @@row_count", 1)[0]
