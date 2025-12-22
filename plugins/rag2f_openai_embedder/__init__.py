"""OpenAI Embedder Plugin for RAG2F"""
import os
from .src.plugin_context import set_plugin_id, get_plugin_id, reset_plugin_id

def get_plugin_path() -> str:
    """Return the absolute path to the rag2f_openai_embedder plugin folder.
    
    This function is called by RAG2F's entry point discovery mechanism
    to locate the plugin directory when installed via pip/uv.
    
    Returns:
        str: Absolute path to the plugin folder containing plugin.json
    """
    return os.path.dirname(os.path.abspath(__file__))

__all__ = [
    'get_plugin_path',
    'set_plugin_id',
    'get_plugin_id',
    'reset_plugin_id',
]
