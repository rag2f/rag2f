# Spock Configuration System for RAG2F

## Overview

Spock is the centralized configuration management system for RAG2F. It provides a unified, instance-based, and developer-friendly way to load and access configuration from both JSON files and environment variables, supporting both core and plugin-specific settings.

---

## Key Features

- **Unified configuration**: One place for all RAG2F and plugin settings
- **Multiple sources**: Load from JSON files and/or environment variables
- **Priority system**: Environment variables override JSON values
- **Instance-based**: Each RAG2F instance has its own isolated configuration
- **Plugin-friendly**: Plugins access their config via the RAG2F instance
- **Type inference**: ENV values are parsed as int, float, bool, JSON, or string
- **No global state**: Safe for testing and multiple RAG2F instances

---

## Configuration Structure

```json
{
  "rag2f": {
    "embedder_default": "test_embedder"
  },
  "plugins": {
    "azure_openai_embedder": {
      "azure_endpoint": "https://your-resource.openai.azure.com",
      "api_key": "your-api-key",
      "api_version": "2024-02-15-preview",
      "deployment": "text-embedding-ada-002",
      "size": 1536,
      "timeout": 30.0
    }
  }
}
```

---

## Environment Variable Naming

```
RAG2F__<SECTION>__<KEY>__<SUBKEY>...
```

- Prefix: `RAG2F__`
- Separator: Double underscore `__`
- Sections: `RAG2F` for core, `PLUGINS` for plugins
- Example:
  - `RAG2F__RAG2F__EMBEDDER_DEFAULT=azure_openai`
  - `RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY=sk-xxx`
  - `RAG2F__PLUGINS__MY_PLUGIN__DATABASE__HOST=localhost`

Type inference is automatic: numbers, booleans, arrays, and objects are parsed from ENV values if possible.

---

## Usage

### 1. Create a Configuration File (Optional)

Create `config.json` as shown above, or use only environment variables.

### 2. Initialize RAG2F

```python
import asyncio
from rag2f.core.rag2f import RAG2F

async def main():
    # With JSON file
    rag2f = await RAG2F.create(config_path="config.json")
    # Or with environment variables only
    # rag2f = await RAG2F.create()

    # Access core config
    embedder = rag2f.spock.get_rag2f_config("embedder_default")
    # Access plugin config
    plugin_cfg = rag2f.spock.get_plugin_config("azure_openai_embedder")

asyncio.run(main())
```

### 3. Use in Plugins

#### In a Hook Function

```python
from rag2f.core.morpheus.decorators import hook

@hook("rag2f_bootstrap_embedders", priority=10)
def bootstrap_azure_embedder(embedders_registry, rag2f):
    config = rag2f.spock.get_plugin_config("azure_openai_embedder")
    # ... use config ...
    return embedders_registry
```

#### In a Plugin Class

```python
class AzureOpenAIEmbedder:
    def __init__(self, rag2f, plugin_id="azure_openai_embedder"):
        config = rag2f.spock.get_plugin_config(plugin_id)
        self.api_key = config.get("api_key")
        if not self.api_key:
            raise ValueError(f"Missing 'api_key' for {plugin_id}")
        self.timeout = config.get("timeout", 30.0)
```

---

## Configuration Priority

1. **Environment Variables** (highest priority)
2. **JSON File**
3. **Default Values** (lowest priority, in code)

---

## Best Practices

### For Application Developers

- Use JSON for complex, structured configuration
- Use environment variables for secrets (API keys, passwords)
- Add `config.json` to `.gitignore`, commit `config.example.json` as a template

### For Plugin Developers

- Document required configuration keys
- Provide sensible defaults for optional settings
- Validate configuration early (in `__init__`)
- Give clear error messages when configuration is missing

---

## Migration from Old Configuration

**Before:**
```python
embedder = AzureOpenAIEmbedder(config_file="plugins/azure_openai_embedder/config.json")
```

**After:**
```python
embedder = AzureOpenAIEmbedder(rag2f=rag2f, plugin_id="azure_openai_embedder")
```
Move your plugin's config into the main `config.json` under `plugins.<plugin_id>` or use environment variables.

---

## Troubleshooting

- Check if Spock is loaded: `rag2f.spock.is_loaded`
- Verify config file path: `rag2f.spock.config_path`
- Check environment variables: `env | grep RAG2F__`
- Enable debug logging for more info

---

## Examples & Templates

- `config.example.json` — JSON configuration template
- `.env.example` — Environment variable examples
- `plugins/azure_openai_embedder/bootstrap_hook.py` — Plugin usage example

---

## License

See LICENSE file.
