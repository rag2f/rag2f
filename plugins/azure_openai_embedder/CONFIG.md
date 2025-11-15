# Azure OpenAI Embedder Configuration

Questo plugin supporta tre modalità di configurazione (in ordine di priorità):

## 1. Parametri espliciti

```python
from plugins.azure_openai_embedder.embedder import AzureOpenAIEmbedder

embedder = AzureOpenAIEmbedder(
    azure_endpoint="https://your-resource.openai.azure.com",
    api_key="your-api-key",
    api_version="2024-02-15-preview",
    deployment="text-embedding-ada-002",
    size=1536
)
```

## 2. File JSON di configurazione

Crea un file `config.json` nella stessa directory del plugin:

```json
{
  "azure_endpoint": "https://your-resource.openai.azure.com",
  "api_key": "your-api-key-here",
  "api_version": "2024-02-15-preview",
  "deployment": "text-embedding-ada-002",
  "size": 1536,
  "timeout": 30.0,
  "max_retries": 2
}
```

Poi usa l'embedder senza parametri:

```python
embedder = AzureOpenAIEmbedder()
```

### File di configurazione personalizzato

Puoi specificare un file di configurazione diverso:

```python
embedder = AzureOpenAIEmbedder(config_file="/path/to/custom_config.json")
```

### Lista di configurazioni

Per gestire multiple configurazioni (es. dev/prod), usa `config_list.json.example` come riferimento.

## 3. Variabili d'ambiente

Imposta queste variabili d'ambiente:

```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_API_VERSION="2024-02-15-preview"
export AZURE_OPENAI_DEPLOYMENT="text-embedding-ada-002"
export AZURE_OPENAI_SIZE="1536"
export AZURE_OPENAI_TIMEOUT="30.0"
export AZURE_OPENAI_MAX_RETRIES="2"
```

Poi usa l'embedder senza parametri:

```python
embedder = AzureOpenAIEmbedder()
```

## Priorità

I parametri espliciti sovrascrivono il file JSON, che a sua volta sovrascrive le variabili d'ambiente.

## Parametri

- `azure_endpoint` (obbligatorio): URL dell'endpoint Azure OpenAI
- `api_key` (obbligatorio): Chiave API
- `api_version` (obbligatorio): Versione dell'API (es. "2024-02-15-preview")
- `deployment` (obbligatorio): Nome del deployment del modello
- `size` (obbligatorio): Dimensione del vettore di embedding
- `timeout` (opzionale): Timeout in secondi (default: 30.0)
- `max_retries` (opzionale): Numero massimo di retry (default: 2)
