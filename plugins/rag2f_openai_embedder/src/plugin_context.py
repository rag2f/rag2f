"""Plugin context management using ContextVar for thread-safe and async-safe access.

This module provides a thread-safe and async-safe way to store and retrieve
the plugin_id throughout the plugin's lifecycle without passing it as a parameter.

Each thread/async task has its own isolated context, preventing race conditions.
"""

from contextvars import ContextVar
import logging

logger = logging.getLogger(__name__)

# Context variable for plugin_id - each thread/async task has its own isolated value
_current_plugin_id: ContextVar[str | None] = ContextVar('plugin_id', default=None)


def set_plugin_id(plugin_id: str) -> None:
    """Set plugin_id in the current context.
    
    This should be called once when the plugin is initialized (e.g., in bootstrap hook).
    The value will be available to all code running in the same thread/async task.
    
    Args:
        plugin_id: The plugin identifier to store in context.
    """
    logger.debug(f"Setting plugin_id in context: {plugin_id}")
    _current_plugin_id.set(plugin_id)


def get_plugin_id(rag2f=None) -> str:
    """Get plugin_id from context, computing it if needed.
    
    First attempts to retrieve the plugin_id from context. If not set,
    and rag2f is provided, it will compute and cache the plugin_id.
    
    Args:
        rag2f: Optional RAG2F instance to compute plugin_id if not in context.
               Required on first call if plugin_id hasn't been set yet.
    
    Returns:
        The plugin_id string.
    
    Raises:
        RuntimeError: If plugin_id is not in context and rag2f is not provided.
    """
    pid = _current_plugin_id.get()
    if pid is None:
        if rag2f is None:
            raise RuntimeError(
                "Plugin ID not found in context and rag2f instance not provided. "
                "Call set_plugin_id() first or provide rag2f parameter."
            )
        
        # Compute plugin_id using self_plugin_id and cache it
        logger.debug("Plugin ID not in context, computing from rag2f.morpheus.self_plugin_id()")
        pid = rag2f.morpheus.self_plugin_id()
        set_plugin_id(pid)
    
    return pid


def reset_plugin_id() -> None:
    """Reset plugin_id context (useful for testing).
    
    This clears the stored plugin_id from the context.
    """
    logger.debug("Resetting plugin_id in context")
    _current_plugin_id.set(None)
