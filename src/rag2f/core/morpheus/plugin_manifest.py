from typing import Dict
from pydantic import BaseModel

#TODO: pyproject or plugin compile have same info, remove?
# The properties accepted in the [project] section of pyproject.toml are defined by the PEP 621 standard. The main ones are:
# name
# version (o dynamic)
# description
# readme
# requires-python
# license
# authors
# maintainers
# keywords
# classifiers
# urls (can be a dictionary of urls, e.g.: {"Homepage" = "...", "Repository" = "..."})
# dependencies
# optional-dependencies
# You can find the official and detailed description of all properties here:
# https://peps.python.org/pep-0621/



class PluginManifest(BaseModel):
    #id: str id plugin set and defined from Morpheus Plugin class
    name: str
    version: str = "0.0.0"
    thumb: str = None
    tags: str = "Unknown"
    description: str = (
        "Description not found for this plugin."
        "Please create a plugin.json manifest"
        " in the plugin folder."
    )
    author_name: str = "Unknown"
    author_url: str = "Unknown"
    plugin_url: str = "Unknown"
    min_rag2f_version: str = "Unknown"
    max_rag2f_version: str = "Unknown"
