

import os
import inspect
from typing import Any
import logging

# Set up a module-level logger
logger = logging.getLogger(__name__)

def get_project_path():
    """Path to the folder from which the cat was run (contains data, plugins and static folders)"""
    return os.getcwd()

def get_default_plugins_path():
    """Allows exposing the plugins' path."""
    return os.path.join(get_project_path(), "plugins")


