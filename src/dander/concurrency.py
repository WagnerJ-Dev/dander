"""Shared lease-fencing contract for BigQuery mutations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from google.cloud import bigquery

_TABLE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class FencingToken:
    """One run's ownership token for a BigQuery pipeline lease row."""

    lease_table: str
    pipeline_id: str
    run_id: str
    token: int

    def __post_init__(self) -> None:
        if not _TABLE_ID.fullmatch(self.lease_table):
            raise ValueError("Invalid BigQuery lease table")
        if not self.pipeline_id or not self.run_id:
            raise ValueError("Fencing identifiers must be non-empty")
        if isinstance(self.token, bool) or self.token <= 0:
            raise ValueError("Fencing token must be a positive integer")


class OwnershipGuard(Protocol):
    """Verify current lease ownership immediately before a finalizer."""

    @property
    def fence(self) -> FencingToken | None:
        """Return the hosted BigQuery fence, if this backend supports one."""

    def verify(self) -> None:
        """Renew ownership or fail closed."""


def fenced_dml(statement: str, fence: FencingToken) -> str:
    """Fence one DML finalizer by touching its owned lease row transactionally."""
    finalizer = statement.strip().removesuffix(";")
    return f"BEGIN TRANSACTION;\n{fencing_touch_sql(fence)}\n{finalizer};\nCOMMIT TRANSACTION;"


def fencing_touch_sql(fence: FencingToken) -> str:
    """Return the conditional lease-row DML and assertion for an existing transaction."""
    return (
        f"UPDATE `{fence.lease_table}`\n"
        "SET heartbeat_at = heartbeat_at\n"
        "WHERE pipeline_id = @dander_pipeline_id\n"
        "  AND run_id = @dander_run_id\n"
        "  AND fencing_token = @dander_fencing_token\n"
        "  AND lease_expires_at > CURRENT_TIMESTAMP();\n"
        "ASSERT @@row_count = 1 AS 'Dander pipeline lease lost';"
    )


def fencing_job_config(fence: FencingToken) -> bigquery.QueryJobConfig:
    """Bind non-secret lease identity to a fenced BigQuery script."""
    return bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "dander_pipeline_id",
                "STRING",
                fence.pipeline_id,
            ),
            bigquery.ScalarQueryParameter("dander_run_id", "STRING", fence.run_id),
            bigquery.ScalarQueryParameter(
                "dander_fencing_token",
                "INT64",
                fence.token,
            ),
        ]
    )
