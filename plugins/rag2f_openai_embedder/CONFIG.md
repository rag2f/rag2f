# OpenAI Embedder Configuration (Spock)

Questo plugin ora legge la configurazione tramite il sistema centralizzato **Spock** di RAG2F.
La configurazione del plugin deve essere inserita nel file di configurazione principale (o tramite environment variables) sotto il nodo `plugins.<plugin_id>`.

Nota: le API in questo repository si aspettano che il plugin richiami la configurazione usando il `plugin_id` (es. `openai_embedder`) tramite `rag2f.spock.get_plugin_config(plugin_id)`.

## Dove mettere la configurazione

Nel file principale di configurazione (es. `config.json`) la sezione plugin deve avere questa struttura:

```json
{
  "plugins": {
    "openai_embedder": {
      "api_key": "sk-your-api-key-here",
      "model": "text-embedding-3-small",
      "size": 1536,
      "timeout": 30.0,
      "max_retries": 2
    }
  }
}
```

In questo esempio il `plugin_id` è `openai_embedder` e Spock caricherà la configurazione quando il plugin la richiederà.

## Variabili d'ambiente (Spock)

Spock supporta anche le variabili d'ambiente. Il formato è basato su prefissi con doppio underscore per rappresentare la gerarchia.

Esempi per impostare la configurazione del plugin via ENV:

```bash
export RAG2F__PLUGINS__OPENAI_EMBEDDER__API_KEY="sk-your-api-key"
export RAG2F__PLUGINS__OPENAI_EMBEDDER__MODEL="text-embedding-3-small"
export RAG2F__PLUGINS__OPENAI_EMBEDDER__SIZE="1536"
export RAG2F__PLUGINS__OPENAI_EMBEDDER__TIMEOUT="30.0"
export RAG2F__PLUGINS__OPENAI_EMBEDDER__MAX_RETRIES="2"
```

Spock applicherà il parsing dei tipi (int, float, bool, JSON) quando possibile.

## Priorità delle sorgenti

1. **Environment Variables** (massima priorità)
2. **File JSON** (config.json passato a RAG2F)
3. **Valori di default nel codice** (minima priorità)

## Esempio: come il plugin accede alla configurazione

Nel codice il plugin ottiene la sua configurazione così:

```python
plugin_cfg = rag2f.spock.get_plugin_config("openai_embedder")
```

Dopo aver ottenuto `plugin_cfg`, il plugin può validare i campi richiesti e lanciare un errore chiaro se mancano.

## Parametri richiesti

- `api_key` (obbligatorio): Chiave API OpenAI
- `model` (obbligatorio): Nome del modello di embedding (es. `"text-embedding-3-small"`, `"text-embedding-3-large"`, `"text-embedding-ada-002"`)
- `size` (obbligatorio): Dimensione del vettore di embedding (1536 per text-embedding-3-small, 3072 per text-embedding-3-large, 1536 per ada-002)
- `timeout` (opzionale): Timeout in secondi (default: 30.0)
- `max_retries` (opzionale): Numero massimo di retry (default: 2)

## Modelli OpenAI disponibili

- `text-embedding-3-small`: 1536 dimensioni (più economico e veloce)
- `text-embedding-3-large`: 3072 dimensioni (migliore qualità)
- `text-embedding-ada-002`: 1536 dimensioni (modello legacy)

## Differenze con Azure OpenAI

A differenza di Azure OpenAI, il plugin OpenAI standard:
- **Non richiede** `azure_endpoint` (usa l'endpoint pubblico OpenAI)
- **Non richiede** `api_version` (usa automaticamente l'ultima versione)
- **Non richiede** `deployment` (usa direttamente il nome del modello)
- Usa il parametro `model` invece di `deployment`
