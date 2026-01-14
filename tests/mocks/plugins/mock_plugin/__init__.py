"""Mock plugin for RAG2F testing."""

from .plugin_context import get_plugin_id, reset_plugin_id, set_plugin_id

__all__ = [
    "set_plugin_id",
    "get_plugin_id",
    "reset_plugin_id",
]
