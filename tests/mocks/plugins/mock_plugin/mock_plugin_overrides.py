from pydantic import BaseModel
from rag2f.core.morpheus.decorators.plugin_decorator import plugin
from rag2f.core.rag2f import RAG2F



@plugin
def activated(plugin,rag2f_instance: RAG2F):
    plugin.custom_id = plugin.id



