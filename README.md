# rag2f




identifichiamo i nomi delle calssi e variabili con riferimenti a film anni 80 e 90.

input → Johnny5 (Cortocircuito – cerca info, curioso)
manager plugin → Morpheus 
config -> Spock

background → Flux Capacitor (Ritorno al Futuro – ciclico, sempre attivo)
gestore coda → Operator (ispirato a Matrix, ma anni ’90 vibe, gestisce flussi)
archivio → Crystal Chamber (Labyrinth – luogo dove si custodisce)
ricercatore → Indiana Jones (ricerca tesori/informazioni)
gestore grafo → Tron (gestisce la rete, perfetto per grafi)





TODO:
qunaod entra un nuovo messaggio di analisi e anche una ricerca va identificato un id di attività da passare e a cui può essere aggiunte info nei vari passaggi in modo genrico( ogni plugin conosce la sua parte perchè interroga la parte per id plugin )

_create_settings_from_model e simili. non deve creare un file setting.json, ma popolare il sistema setting, se vogliamo. Forse da tolgiere, la parte utile e dichiarare cosa serve come setting.





da spiegare per i plugin e caricare i requirements

vscode ➜ /workspaces/rag2f (main) $ python3 -c "from rag2f.core.morpheus.plugin import Plugin; Plugin.install_requirements('local', 'plugins/azure_openai_embedder')"



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