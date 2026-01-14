# rag2f

rag2f is a plugin-first, entry-point-driven kernel for composing Retrieval-Augmented Generation systems. It provides a small set of registries and hooks so you can assemble your own ingest -> embed -> store -> retrieve -> answer flow without being forced into a single pipeline shape.

## What rag2f is not

rag2f is not a turnkey RAG pipeline. It intentionally does not implement a full end-to-end app. Pipelines live in plugins or in your own application.

## The problem it solves

RAG systems depend on volatile infrastructure (vector databases, LLM SDKs, document stores, graph engines). That volatility creates two problems:

- Supply-chain risk: dependency churn can break your app or force a migration.
- Architecture rigidity: a single pipeline hides backend-specific power and makes swaps painful.

rag2f solves this by acting as a small, stable kernel with a strict plugin boundary. It keeps the core minimal and pushes optional complexity to plugins. The result is composability with explicit contracts and controlled coupling.

## The value of plugin-scoped dependencies

Each plugin can ship and load its own dependencies. The core stays small and only includes what is strictly necessary. This provides real value:

- Fewer dependencies in the base install reduces attack surface and supply-chain risk.
- You only install what you actually use.
- Dependencies stay isolated to the plugin that needs them.

Many frameworks that support multiple LLM providers or storage backends pull in all related dependencies even when unused. rag2f avoids that by design: plugins carry their own dependency footprint, and the kernel stays lean.

## High-level architecture

```
               +-----------------------+
               |   Your Application    |
               +-----------+-----------+
                           |
                    RAG2F facade
                           |
  +------------+-----------+-----------+------------+
  |            |                       |            |
Johnny5     Morpheus                Spock       OptimusPrime
Input       Plugins + Hooks         Config      Embedder registry
Manager     (entry points + FS)                (embedders from plugins)
                           |
                           +-------- XFiles --------+
                                    Repository registry
                               (SQL, vector DB, graph, etc.)
```

## Plugin discovery model

rag2f discovers plugins in two places:

- Python entry points: `entry_points(group="rag2f.plugins")`
- Filesystem: local `plugins/` folders

Precedence is intentional:

- Entry points win over filesystem to avoid ambiguity (installed plugin overrides local).
- Plugin IDs are deduplicated to prevent "same hook counted twice".
- Hook modules are loaded with stable namespaces to avoid double-import side effects.

This model supports both local development and packaged distribution without conflicts.

## Core components (narrative naming is intentional)

The names are constraints on design, not jokes. Registries and managers are the core pattern:

- Johnny5: input manager. Small, deterministic input handlers.
- Morpheus: plugin and hook manager. The "reality adapter" that loads plugins and executes hooks.
- Spock: configuration manager. Central, instance-scoped config (JSON + env).
- OptimusPrime: embedder registry. Embedders are provided by plugins.
- XFiles: repository registry. The truth is out there.

## Plugin-first architecture

Plugins are the primary extension mechanism. A plugin can provide:

- Embedders (via OptimusPrime hooks)
- Repositories (via XFiles hooks)
- Additional hook implementations that change behavior

Entry points are the production path; filesystem plugins are a local dev path. The core never hardcodes a specific backend.

Included plugin examples:

- `plugins/rag2f_azure_openai_embedder`: embedder plugin using Spock for config.
- `plugins/rag2f_macgyver`: in-memory plugin for fast local experiments.

## XFiles deep dive (repository manager)

XFiles is the registry for heterogeneous repositories: SQL, vector DBs, document stores, graphs, or hybrids.

rag2f intentionally does not flatten tools into a lowest-common-denominator API. Instead, it enforces a minimal contract and allows opt-in advanced features.

XFiles exists in this repo and is tested extensively under `tests/core/xfiles`.

### What is a repository in rag2f terms

A repository is a plugin that implements one or more of these protocols:

- BaseRepository: minimal CRUD + capability declaration + native escape hatch.
- QueryableRepository: adds QuerySpec-based `find()`.
- VectorSearchRepository: adds `vector_search()`.
- GraphTraversalRepository: adds `traverse()`.

The protocol boundaries are explicit, and capability declarations tell you which features are safe to use.

### Capabilities and validation

Repositories declare capabilities (filter ops, pagination, vector search, native access). QuerySpec validation uses those capabilities to detect unsupported operators and invalid fields early. This keeps behavior consistent and prevents silent backend fallbacks.

### Native escape hatch

If a backend has powerful native operations, expose them. A repository can surface native handles via `native()` / `as_native()` instead of hiding them behind a lowest-common-denominator API. This keeps rag2f honest about backend-specific power.

### Minimal usage (conceptual)

```python
from rag2f.core.xfiles import XFiles, QuerySpec, eq, and_

xfiles = XFiles()
xfiles.register("users_db", users_repo, meta={"type": "postgresql", "domain": "users"})

repo = xfiles.get("users_db")
query = QuerySpec(
    select=["id", "email"],
    where=and_(eq("status", "active"), eq("tier", "pro")),
    order_by=["-created_at"],
    limit=10,
)
rows = repo.find(query)
```

### Native access example (conceptual)

```python
client = repo.native("primary")
client.execute("EXPLAIN ANALYZE SELECT ...")
```

## Embedders deep dive (OptimusPrime)

OptimusPrime is the embedder registry. Embedders are contributed by plugins via hooks (for example, `rag2f_bootstrap_embedders`). The registry enforces protocol compliance and prevents accidental overrides.

The default embedder is selected via Spock configuration (`rag2f.embedder_default`). If only one embedder is registered, it becomes default automatically.

```python
embedder = rag2f.optimus_prime.get_default()
vector = embedder.getEmbedding("hello")
```

## Spock configuration (overview)

Spock provides instance-scoped configuration from JSON and environment variables with a clear precedence model. It is the source of truth for both core and plugin settings.

- JSON config for structured settings
- ENV for secrets and overrides
- ENV overrides JSON

See `SPOCK_README.md` and `config.example.json` for concrete formats.

## How to think about rag2f

A useful mental model is "registries + hooks":

- Registries store and validate concrete implementations (embedders, repositories).
- Hooks let plugins contribute those implementations.
- The core stays small and stable; complexity lives at the edges.

This lets you build a RAG pipeline that fits your constraints without forcing other teams to adopt the same stack.

## Development

This repo supports both Dev Containers and a local `venv` workflow. The recommended default is a project-local `.venv` so everyone uses the same commands.

### venv-first setup

```bash
bash scripts/bootstrap-venv.sh
source .venv/bin/activate
```

### Dev Container

The Dev Container runs the same bootstrap script on creation, so you still end up with a `.venv` in the workspace.

Install dev dependencies (manual alternative):

```bash
pip install -e '.[dev]'
```

Ruff is the single tool used for linting, import sorting, and formatting.

Run Ruff:

```bash
ruff check src tests
ruff check --fix src tests
ruff format src tests
ruff format --check src tests
```

Enable pre-commit hooks:

```bash
pre-commit install
pre-commit run --all-files
```

### Tests

Install dev dependencies:

```bash
pip install -e '.[dev]'
```

Run tests:

```bash
pytest
```

## Status and roadmap

rag2f is incomplete by design. The kernel focuses on pluggable registries and hook-based composition. A full RAG pipeline is intentionally outside the core.

Future direction (conceptual, not implemented here):

- Higher-level orchestration patterns built on hooks.
- Optional workers/queues/DAG execution as separate packages or plugins.

## License

rag2f is open source and distributed under GPL-3.0.
