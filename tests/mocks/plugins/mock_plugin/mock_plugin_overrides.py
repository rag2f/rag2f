from pydantic import BaseModel
from rag2f.core.morpheus.decorators.plugin_decorator import plugin



@plugin
def activated(plugin):
    plugin.custom_id = plugin.id



