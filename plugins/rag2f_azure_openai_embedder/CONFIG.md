# Azure OpenAI Embedder Configuration (Spock)

Questo plugin ora legge la configurazione tramite il sistema centralizzato **Spock** di RAG2F.
La configurazione del plugin deve essere inserita nel file di configurazione principale (o tramite environment variables) sotto il nodo `plugins.<plugin_id>`.

Nota: le API in questo repository si aspettano che il plugin richiami la configurazione usando il `plugin_id` (es. `azure_openai_embedder`) tramite `rag2f.spock.get_plugin_config(plugin_id)`.

## Dove mettere la configurazione

Nel file principale di configurazione (es. `config.json`) la sezione plugin deve avere questa struttura:

```json
{
  "plugins": {
    "azure_openai_embedder": {
      "azure_endpoint": "https://your-resource.openai.azure.com",
      "api_key": "your-api-key-here",
      "api_version": "2024-02-15-preview",
      "deployment": "text-embedding-ada-002",
      "size": 1536,
      "timeout": 30.0,
      "max_retries": 2
    }
  }
}
```

In questo esempio il `plugin_id` è `azure_openai_embedder` e Spock caricherà la configurazione quando il plugin la richiederà.

## Variabili d'ambiente (Spock)

Spock supporta anche le variabili d'ambiente. Il formato è basato su prefissi con doppio underscore per rappresentare la gerarchia.

Esempi per impostare la configurazione del plugin via ENV:

```bash
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__AZURE_ENDPOINT="https://your-resource.openai.azure.com"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY="your-api-key"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_VERSION="2024-02-15-preview"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__DEPLOYMENT="text-embedding-ada-002"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__SIZE="1536"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__TIMEOUT="30.0"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__MAX_RETRIES="2"
```

Spock applicherà il parsing dei tipi (int, float, bool, JSON) quando possibile.

## Priorità delle sorgenti

1. **Environment Variables** (massima priorità)
2. **File JSON** (config.json passato a RAG2F)
3. **Valori di default nel codice** (minima priorità)

## Esempio: come il plugin accede alla configurazione

Nel codice il plugin ottiene la sua configurazione così:

```python
plugin_cfg = rag2f.spock.get_plugin_config("azure_openai_embedder")
```

Dopo aver ottenuto `plugin_cfg`, il plugin può validare i campi richiesti e lanciare un errore chiaro se mancano.

## Parametri richiesti

- `azure_endpoint` (obbligatorio): URL dell'endpoint Azure OpenAI
- `api_key` (obbligatorio): Chiave API
- `api_version` (obbligatorio): Versione dell'API (es. `"2024-02-15-preview"`)
- `deployment` (obbligatorio): Nome del deployment del modello
- `size` (obbligatorio): Dimensione del vettore di embedding
- `timeout` (opzionale): Timeout in secondi (default: 30.0)
- `max_retries` (opzionale): Numero massimo di retry (default: 2)

