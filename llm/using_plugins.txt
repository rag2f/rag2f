# Using Plugins with RAG2F

Guide to installing, configuring, and using plugins to extend RAG2F.

## Plugin Discovery Order

RAG2F discovers plugins from **two sources** in this priority order:

1. **Entry Points** (pip packages) — HIGHEST PRIORITY
   - Installed via `pip install` or `uv add`
   - Defined in `pyproject.toml` under `[project.entry-points."rag2f.plugins"]`

2. **Filesystem** (`plugins/` folder) — LOCAL DEVELOPMENT  
   - Local directories in your project
   - Default path: `./plugins/`

**Important:** Entry points WIN if the same plugin ID exists in both sources.

### Why This Order?

- **Installed packages override local** — avoids "which version am I running?" confusion
- **Plugin IDs are deduplicated** — same ID can't register twice
- **Predictable behavior** — production (entry points) takes precedence over dev (filesystem)

---

## Installing Plugins

### From PyPI

```bash
# Install a RAG2F plugin package
pip install rag2f-azure-openai-embedder
pip install rag2f-qdrant-store

# Or with rag2f extras
pip install rag2f[azure-openai]
```

Once installed, plugins are **automatically discovered** via entry points.

### From Local Folder

Place plugin directory in your `plugins/` folder:

```
your_project/
├── main.py
├── config.json
└── plugins/
    ├── my_custom_plugin/
    │   ├── __init__.py
    │   ├── plugin.toml
    │   └── hooks.py
    └── another_plugin/
        └── ...
```

---

## Configuring RAG2F to Use Plugins

### Specify plugins_folder

```python
from rag2f.core.rag2f import RAG2F

# Default: looks for ./plugins/
rag2f = await RAG2F.create()

# Custom folder
rag2f = await RAG2F.create(plugins_folder="./my_plugins/")

# Multiple projects can share plugins
rag2f = await RAG2F.create(plugins_folder="/shared/rag2f_plugins/")
```

### Plugin Configuration

Plugins read config from Spock. Set in `config.json`:

```json
{
  "rag2f": {
    "embedder_default": "azure_openai"
  },
  "plugins": {
    "azure_openai_embedder": {
      "endpoint": "https://your-resource.openai.azure.com/",
      "deployment_name": "text-embedding-ada-002",
      "api_version": "2023-05-15"
    },
    "qdrant_store": {
      "host": "localhost",
      "port": 6333,
      "collection": "documents"
    }
  }
}
```

### Secrets via Environment

**Never commit secrets to config.json.** Use environment variables:

```bash
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY=sk-xxx
export RAG2F__PLUGINS__QDRANT_STORE__API_KEY=qdrant-key
```

---

## Verifying Plugin Discovery

### Check Loaded Plugins

```python
rag2f = await RAG2F.create(plugins_folder="./plugins/")

# List all loaded plugins
print("Loaded plugins:")
for plugin_id in rag2f.morpheus.plugins:
    print(f"  - {plugin_id}")

# Check specific plugin
if rag2f.morpheus.plugin_exists("my_plugin"):
    plugin = rag2f.morpheus.get_plugin("my_plugin")
    print(f"Plugin {plugin.id} loaded from {plugin.path}")
```

### Check Registered Hooks

```python
# List all hooks
print("Registered hooks:")
for hook_name, hooks in rag2f.morpheus.hooks.items():
    print(f"  {hook_name}:")
    for h in hooks:
        print(f"    - {h.plugin_id} (priority={h.priority})")
```

### Check Embedders (OptimusPrime)

```python
# List registered embedders
print("Embedders:", rag2f.optimus_prime.list_keys())

# Get default
try:
    embedder = rag2f.optimus_prime.get_default()
    print(f"Default embedder: {embedder}, size={embedder.size}")
except LookupError as e:
    print(f"No default embedder: {e}")
```

### Check Repositories (XFiles)

```python
# List registered repositories
print("Repositories:", rag2f.xfiles.list_ids())

# Check specific
if rag2f.xfiles.has("vectors"):
    caps = rag2f.xfiles.get_capabilities("vectors")
    print(f"Vector search supported: {caps.vector_search.supported}")
```

---

## Plugin Loading Lifecycle

When `RAG2F.create()` is called:

1. **Initialize core modules** — Spock, Johnny5, IndianaJones, OptimusPrime, XFiles, Morpheus
2. **Load configuration** — JSON file first, then ENV overrides
3. **morpheus.find_plugins()** discovers plugins:
   - Load from entry points (pip packages) → `plugin.activate()` for each
   - Load from filesystem (`plugins/`) → `plugin.activate()` for each (skip if ID already exists)
4. **refresh_caches()** — Index all hooks by name, sort by priority (higher first)
5. **Execute bootstrap hooks** — e.g., `rag2f_bootstrap_embedders` to register embedders

---

## Using Plugin-Provided Features

### Embedders

Plugins register embedders via `rag2f_bootstrap_embedders` hook:

```python
# Get the default embedder (configured via rag2f.embedder_default)
embedder = rag2f.optimus_prime.get_default()
vector = embedder.getEmbedding("Hello world")

# Get specific embedder
azure = rag2f.optimus_prime.get("azure_openai")
if azure:
    vector = azure.getEmbedding("test")
```

### Repositories

Plugins register repositories via bootstrap hooks:

```python
# Get repository
result = rag2f.xfiles.execute_get("qdrant")
if result.is_ok() and result.repository:
    repo = result.repository
    
    # Vector search
    results = repo.vector_search(embedding_vector, k=10)
    
    # Native access
    client = repo.native("client")
```

### Processing Pipeline

Plugins extend input processing via hooks:

```python
# This triggers all handle_text_foreground hooks
result = rag2f.johnny5.execute_handle_text_foreground("Process this text")

if result.is_ok():
    print(f"Processed with ID: {result.track_id}")
```

---

## Optional: Troubleshooting

### Plugin Not Loading

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now create RAG2F - will show plugin discovery logs
rag2f = await RAG2F.create(plugins_folder="./plugins/")
```

Look for:
- `✅ Loaded plugin 'xxx' from entry point`
- `📁 Loaded plugin 'xxx' from filesystem`
- `Plugin 'xxx' already loaded` (duplicate ID)

### Hook Not Executing

```python
# Check if hook is registered
if "handle_text_foreground" in rag2f.morpheus.hooks:
    hooks = rag2f.morpheus.hooks["handle_text_foreground"]
    print(f"Registered hooks: {[(h.plugin_id, h.priority) for h in hooks]}")
else:
    print("No hooks registered for handle_text_foreground")
```

### Config Not Reading

```python
# Check if plugin config is loaded
config = rag2f.spock.get_plugin_config("my_plugin")
print(f"Plugin config: {config}")

# Check ENV override
import os
print(f"ENV: {os.environ.get('RAG2F__PLUGINS__MY_PLUGIN__API_KEY', 'not set')}")
```

---

## Example: Complete Setup

### Project Structure

```
my_rag_app/
├── main.py
├── config.json
└── plugins/
    └── my_custom_processor/
        ├── __init__.py
        ├── plugin.toml
        └── hooks.py
```

### config.json

```json
{
  "rag2f": {
    "embedder_default": "azure_openai"
  },
  "plugins": {
    "azure_openai_embedder": {
      "endpoint": "https://my-resource.openai.azure.com/",
      "deployment_name": "text-embedding-ada-002"
    },
    "my_custom_processor": {
      "max_length": 1000
    }
  }
}
```

### main.py

```python
import asyncio
from rag2f.core.rag2f import RAG2F

async def main():
    # Create RAG2F with plugins
    rag2f = await RAG2F.create(
        config_path="config.json",
        plugins_folder="./plugins/"
    )
    
    # Verify setup
    print(f"Plugins: {list(rag2f.morpheus.plugins.keys())}")
    print(f"Embedders: {rag2f.optimus_prime.list_keys()}")
    
    # Use the system
    result = rag2f.johnny5.execute_handle_text_foreground(
        "Process this document text"
    )
    
    if result.is_ok():
        print(f"Success! Track ID: {result.track_id}")
    else:
        print(f"Error: {result.detail.message}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Environment

```bash
# Set secrets
export RAG2F__PLUGINS__AZURE_OPENAI_EMBEDDER__API_KEY=your-key

# Run
python main.py
```
