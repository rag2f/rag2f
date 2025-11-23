"""MacGyver Plugin for RAG2F - Lightweight in-memory experimentation."""
import os

def get_plugin_path() -> str:
    """Return the absolute path to the macgyver plugin folder.
    
    This function is called by RAG2F's entry point discovery mechanism
    to locate the plugin directory when installed via pip/uv.
    
    Returns:
        str: Absolute path to the plugin folder containing plugin.json
        
    Note:
        When installed as a package, this __init__.py is in rag2f_macgyver/,
        but we need to return the parent directory (macgyver/) which contains
        the actual plugin.json and src/ for the plugin to work correctly.
        
        In a distributed package, the entire macgyver/ folder structure
        (including plugin.json, src/, settings.json) is packaged, so the
        parent of this file is the plugin root.
    """
    # Return the parent directory (macgyver/) not this package directory (rag2f_macgyver/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

__all__ = ['get_plugin_path']
