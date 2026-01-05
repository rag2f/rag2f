# rag2f






TODO:


_create_settings_from_model e simili. non deve creare un file setting.json, ma popolare il sistema setting, se vogliamo. Forse da tolgiere, la parte utile e dichiarare cosa serve come setting.





per notebook da capire una soluzione del genere
from rag2f import RAG2F
from rag2f.core.morpheus.decorators import hook

# 1. Definisci gli hook PRIMA
@hook("rag2f_bootstrap_embedders", priority=5)
def my_embedder_hook(registry, rag2f):
    registry["my_embedder"] = MyEmbedder()
    return registry

# 2. Passa gli hook al create()
rag2f = await RAG2F.create(hooks=[my_embedder_hook])