
from rag2f.core.morpheus.decorators import hook


@hook
def rag2f_bootstrap_embedders(embedder_registry, rag2f):
    return embedder_registry
