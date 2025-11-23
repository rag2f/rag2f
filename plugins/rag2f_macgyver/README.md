# MacGyver Plugin for RAG2F

MacGyver is your go-to plugin for quick, local experiments. Lightweight and fully in-memory, it runs only on your machine with no external dependencies or persistence. Perfect for isolated tests and rapid prototypes, it does more with less—just like its namesake.

## Installation

### From PyPI (when published)
```bash
pip install rag2f-macgyver
# or with uv
uv pip install rag2f-macgyver
```

### From source (development)
```bash
pip install -e /path/to/plugins/macgyver
# or with uv
uv pip install -e /path/to/plugins/macgyver
```

## Usage

Once installed, the plugin is automatically discovered by RAG2F through entry points. No additional configuration is needed.

```python
from rag2f.core.morpheus import Morpheus

# Morpheus will automatically discover and load macgyver
morpheus = await Morpheus.create()
```

## Features

- 🚀 Lightweight and fast
- 💾 Fully in-memory operation
- 🔌 No external dependencies
- 🧪 Perfect for rapid prototyping and testing

## License

GPL-3.0
