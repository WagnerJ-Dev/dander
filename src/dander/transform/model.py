"""Transform engine primitives — our owned dbt-replacement.

Per the Decision Log we build this ourselves. A model is SQL + a YAML sidecar. ``ref('other')``
calls are parsed (via sqlglot / Jinja) to build a dependency DAG, topologically sorted, then
executed with materializations that reuse the writer's write patterns. Generic tests (not-null,
unique, accepted-values, relationships) compile to assertion queries. The model YAML is the
metadata spine — it also feeds the catalog and semantic registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Materialization(str, Enum):
    VIEW = "view"
    TABLE = "table"
    INCREMENTAL = "incremental"


@dataclass
class Model:
    """A single transform model: SQL file + its declared metadata."""

    name: str
    sql_path: Path
    materialization: Materialization = Materialization.VIEW
    refs: list[str] = field(default_factory=list)


def parse_refs(sql: str) -> list[str]:
    """Extract ``ref('name')`` dependencies from model SQL to build the DAG."""
    raise NotImplementedError("DANDER: parse ref() calls with sqlglot/Jinja")
