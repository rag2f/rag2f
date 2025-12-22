
from rag2f.core.morpheus.decorators import hook
from rag2f.core.protocols.embedder import register
from .plugin_context import get_plugin_id

class MockEmbedder:
    """Mock embedder per i test."""
    @property
    def size(self) -> int:
        return 3

    def getEmbedding(self, text: str, *, normalize: bool = False):
        return [0.1, 0.2, 0.3]  # Mock embedding

@hook
def rag2f_bootstrap_embedders(embedder_registry, rag2f):
    """Mock hook che registra un embedder di test nel registry usando la funzione register."""
    plugin_id = get_plugin_id(rag2f)
    register(embedder_registry, plugin_id, MockEmbedder())
    return embedder_registry
