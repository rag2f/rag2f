# Azure OpenAI Embedder Configuration (Spock)

This plugin now reads configuration through RAG2F's centralized **Spock** system.
The plugin configuration must be placed in the main configuration file (or via environment variables) under `plugins.<plugin_id>`.

Note: the APIs in this repository expect the plugin to request configuration using the `plugin_id` (e.g., `azure_openai_embedder`) via `rag2f.spock.get_plugin_config(plugin_id)`.

## Where to place the configuration

In the main configuration file (e.g., `config.json`) the plugin section should have this structure:

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

In this example the `plugin_id` is `azure_openai_embedder` and Spock will load the configuration when the plugin requests it.

## Environment variables (Spock)

Spock also supports environment variables. The format uses double-underscore prefixes to represent the hierarchy.

Examples to set the plugin configuration via ENV:

```bash
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__AZURE_ENDPOINT="https://your-resource.openai.azure.com"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY="your-api-key"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_VERSION="2024-02-15-preview"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__DEPLOYMENT="text-embedding-ada-002"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__SIZE="1536"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__TIMEOUT="30.0"
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__MAX_RETRIES="2"
```

Spock will parse types (int, float, bool, JSON) when possible.

## Source priority

1. **Environment Variables** (highest priority)
2. **JSON file** (`config.json` passed to RAG2F)
3. **Default values in code** (lowest priority)

## Example: how the plugin accesses configuration

In code the plugin gets its configuration like this:

```python
plugin_cfg = rag2f.spock.get_plugin_config("azure_openai_embedder")
```

After obtaining `plugin_cfg`, the plugin can validate required fields and raise a clear error if they are missing.

## Required parameters

- `azure_endpoint` (required): URL of the Azure OpenAI endpoint
- `api_key` (required): API key
- `api_version` (required): API version (e.g., `"2024-02-15-preview"`)
- `deployment` (required): Model deployment name
- `size` (required): Embedding vector size
- `timeout` (optional): Timeout in seconds (default: 30.0)
- `max_retries` (optional): Maximum retries (default: 2)
