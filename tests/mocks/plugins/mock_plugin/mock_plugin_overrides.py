from rag2f.core.morpheus.decorators.plugin_decorator import plugin
from rag2f.core.rag2f import RAG2F


class MockEmbedder:
    """Simple embedder used by the mock plugin tests."""

    @property
    def size(self) -> int:
        return 3

    def getEmbedding(self, text: str, *, normalize: bool = False):
        return [0.1, 0.2, 0.3]


@plugin
def activated(plugin, rag2f_instance: RAG2F):
    plugin.custom_id = plugin.id
    embedder_manager = rag2f_instance.optimus_prime
    if not embedder_manager.has(plugin.id):
        embedder_manager.register(plugin.id, MockEmbedder())



