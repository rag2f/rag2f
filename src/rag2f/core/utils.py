"""Small core utilities used across the project."""

import logging
import os

# Set up a module-level logger
logger = logging.getLogger(__name__)


def get_project_path():
    """Return the current working directory used as project root."""
    return os.getcwd()


def get_default_plugins_path():
    """Allows exposing the plugins' path."""
    return os.path.join(get_project_path(), "plugins")
