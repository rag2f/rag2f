# rag2f




identifichiamo i nomi delle calssi e variabili con riferimenti a film anni 80 e 90.

input → Johnny5 (Cortocircuito – cerca info, curioso)
background → Flux Capacitor (Ritorno al Futuro – ciclico, sempre attivo)
gestore coda → Operator (ispirato a Matrix, ma anni ’90 vibe, gestisce flussi)
manager plugin → Morpheus 
archivio → Crystal Chamber (Labyrinth – luogo dove si custodisce)
ricercatore → Indiana Jones (ricerca tesori/informazioni)
gestore grafo → Tron (gestisce la rete, perfetto per grafi)





TODO:
qunaod entra un nuovo messaggio di analisi e anche una ricerca va identificato un id di attività da passare e a cui può essere aggiunte info nei vari passaggi in modo genrico( ogni plugin conosce la sua parte perchè interroga la parte per id plugin )







da spiegare per i plugin e caricare i requirements

vscode ➜ /workspaces/rag2f (main) $ python3 -c "from rag2f.core.morpheus.plugin import Plugin; Plugin.install_requirements('local', 'plugins/azure_openai_embedder')"