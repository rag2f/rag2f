"""Decorators used by the plugin system."""

from .hook import PillHook, hook
from .plugin_decorator import plugin as plugin

__all__ = ["hook", "PillHook", "plugin"]
