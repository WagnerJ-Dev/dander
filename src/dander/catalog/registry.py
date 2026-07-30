"""Atomic local semantic-registry publication."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from pathlib import Path


class SemanticRegistryError(OSError):
    """Raised when a local semantic registry cannot be written atomically."""


class SemanticRegistryPublisher:
    """Write deterministic, versioned JSON for agents and local tooling."""

    def publish(self, manifest: dict[str, object], output: Path) -> Path:
        """Write a complete manifest atomically and return its path."""
        temporary = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            temporary.replace(output)
        except OSError as error:
            raise SemanticRegistryError(f"Cannot write semantic registry: {output}") from error
        finally:
            temporary.unlink(missing_ok=True)
        return output
