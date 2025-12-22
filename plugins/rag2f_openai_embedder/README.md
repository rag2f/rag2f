# RAG2F OpenAI Embedder Plugin

Plugin per l'integrazione di OpenAI embeddings in RAG2F.

## Struttura del Plugin

```
rag2f_openai_embedder/
├── __init__.py                    # Entry point del plugin
├── plugin.json                    # Metadata del plugin
├── settings.json                  # Settings (vuoto)
├── pyproject.toml                 # Configurazione package Python
├── config.json.example            # Esempio di configurazione
├── CONFIG.md                      # Documentazione configurazione
├── src/
│   ├── __init__.py               # Package src
│   ├── plugin_context.py         # Gestione plugin_id thread-safe
│   ├── embedder.py               # Implementazione OpenAIEmbedder
│   └── bootstrap_hook.py         # Hook di bootstrap
└── test/
    ├── conftest.py               # Configurazione pytest
    ├── test_embedder_unit.py     # Unit test embedder
    └── test_bootstrap_hook.py    # Test bootstrap hook
```

## Parametri di Configurazione

### Obbligatori
- **api_key**: Chiave API OpenAI (es. `"sk-..."`)
- **model**: Nome del modello di embedding
  - `"text-embedding-3-small"` (1536 dim, economico)
  - `"text-embedding-3-large"` (3072 dim, alta qualità)
  - `"text-embedding-ada-002"` (1536 dim, legacy)
- **size**: Dimensione del vettore (1536 o 3072)

### Opzionali
- **timeout**: Timeout richieste in secondi (default: 30.0)
- **max_retries**: Numero massimo di retry (default: 2)

## Differenze rispetto ad Azure OpenAI

Il plugin OpenAI standard differisce da Azure OpenAI per:

1. **NON richiede** `azure_endpoint` (usa endpoint pubblico OpenAI)
2. **NON richiede** `api_version` (usa automaticamente l'ultima versione)
3. **NON richiede** `deployment` (usa direttamente `model`)
4. Utilizza la classe `OpenAI` invece di `AzureOpenAI`

## Configurazione

### Tramite JSON (config.json)

```json
{
  "plugins": {
    "openai_embedder": {
      "api_key": "sk-your-api-key",
      "model": "text-embedding-3-small",
      "size": 1536,
      "timeout": 30.0,
      "max_retries": 2
    }
  }
}
```

### Tramite Variabili d'Ambiente

```bash
export RAG2F__PLUGINS__OPENAI_EMBEDDER__API_KEY="sk-your-api-key"
export RAG2F__PLUGINS__OPENAI_EMBEDDER__MODEL="text-embedding-3-small"
export RAG2F__PLUGINS__OPENAI_EMBEDDER__SIZE="1536"
export RAG2F__PLUGINS__OPENAI_EMBEDDER__TIMEOUT="30.0"
export RAG2F__PLUGINS__OPENAI_EMBEDDER__MAX_RETRIES="2"
```

## Installazione

```bash
cd plugins/rag2f_openai_embedder
pip install -e .
```

## Test

```bash
cd plugins/rag2f_openai_embedder
pytest test/
```

## Utilizzo nel Codice

Il plugin si registra automaticamente tramite il bootstrap hook. Una volta configurato, l'embedder sarà disponibile in RAG2F con l'ID `openai_embedder`.

```python
# Il plugin si carica automaticamente
rag2f = await RAG2F.create(
    plugins_folder="plugins/",
    config=config
)

# L'embedder è disponibile via OptimusPrime
embedder = rag2f.optimus_prime.get("rag2f_openai_embedder")
vector = embedder.getEmbedding("Hello, world!")
```

## Validazione

Il plugin include validazione completa:
- Verifica parametri obbligatori
- Type checking (size, timeout, max_retries)
- Logging dettagliato
- Error handling appropriato

## Test Coverage

- ✅ Validazione configurazione
- ✅ Inizializzazione client
- ✅ Chiamate API corrette
- ✅ Edge cases (stringhe vuote, Unicode)
- ✅ Gestione errori
- ✅ Diversi modelli OpenAI
- ✅ Bootstrap hook
