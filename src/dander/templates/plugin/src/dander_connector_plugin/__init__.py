"""__DISPLAY_NAME__ connector plugin for Dander."""

from __PACKAGE_NAME__.plugin import create_plugin
from __PACKAGE_NAME__.source import __SOURCE_CLASS__

__all__ = ["__SOURCE_CLASS__", "create_plugin"]
