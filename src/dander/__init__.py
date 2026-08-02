"""Dander — an opinionated, GCP-native data platform (ingest + transform + catalog).

Keep this module import-light: importing ``dander`` must not require the heavy optional
dependencies. Import from the subpackages (``dander.ingestion``, ``dander.writer``, ...) directly.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dander-platform")
except PackageNotFoundError:  # pragma: no cover - only an unpackaged source tree
    __version__ = "0+unknown"
