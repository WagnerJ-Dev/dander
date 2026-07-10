"""Metadata spine — 'define once, project everywhere'.

One model/source YAML projects to executable SQL **and** data-catalog aspects (Dataplex) **and** a
semantic/agent registry. This is a core differentiator (see ``steering/00-project-overview.md``):
the same metadata that compiles the SQL also documents the asset for the catalog and the agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class CatalogPublisher(ABC):
    """Publishes/refreshes catalog aspects for a table or model."""

    @abstractmethod
    def publish(self, asset: str, aspects: Mapping[str, Any]) -> None:
        """Upsert ``aspects`` (source system, sensitivity, last-refreshed, …) for ``asset``."""
