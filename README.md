# rag2f

Plugin-first RAG playground with 80s/90s movie nicknames to keep things fun:
- Input manager: Johnny5 (Short Circuit) – grabs input and asks for “more input”.
- Plugin manager: Morpheus – discovers plugins and runs hooks.
- Config: Spock – logical, consistent settings.
- Background loop: Flux Capacitor – always-on cycle.
- Queue operator: Operator – handles message flow.
- Archive: Crystal Chamber (Labyrinth) – stores artifacts.
- Researcher: Indiana Jones – hunts for information.
- Graph manager: Tron – manages networks/graphs.

## Core ideas
- Everything important is a plugin: plugins declare hooks, embedders, repositories.
- Hooks are semantic steps (not pipelines). Morpheus executes hooks, highest priority first.
- Johnny5 routes input through hooks, letting plugins create IDs, detect duplicates, and handle ingestion.
- Spock loads config from JSON/env; OptimusPrime keeps embedders; XFile keeps repositories.

## Async agents (Flux Capacitor + Operator)
- Redis is the only backend for queue, state, and polling.
- Canonical keys: `queue:{plugin_id}`, `job:{job_id}`, `job_children:{job_id}`, `job_parent:{job_id}`, `input_root:{input_id}`.
- Queue messages are JSON with `{job_id, parent_job_id, root_input_id, plugin_id, hook, payload_ref, metadata}` — no raw payloads in messages.
- `RedisJobStore` persists jobs and trees; `RedisQueue` pushes/pops messages; `JobStatusView` enforces completion: DONE only when the node and all descendants are DONE; any RUNNING/PENDING below reports RUNNING; any FAILED below reports FAILED.
- `AgentWorker` is stateless: BRPOP on `queue:{plugin_id}`, resolve exactly one hook for that plugin, execute it, and optionally fan out children (`ChildJobRequest`) that share the same `root_input_id`.
- Fan-out + polling are tree-based: children are registered under `job_children:{parent}`; `RedisJobStore.get_status_view(job_id)` returns the tree with status/progress.

### Quick example (with fakeredis)
```python
import fakeredis.aioredis
from rag2f import RAG2F
from rag2f.core.flux_capacitor import RedisJobStore, RedisQueue, AgentWorker

redis = fakeredis.aioredis.FakeRedis()
rag2f = await RAG2F.create(plugins_folder="tests/mocks/plugins/")
store, queue = RedisJobStore(redis), RedisQueue(redis)

job = await store.create_job(
    plugin_id="my_plugin",
    hook="generate_embedding_raw_input_message",
    root_input_id="input-uuid",
    payload_ref={"repository": "raw_inputs", "id": "42"},
)
await queue.enqueue(job)

worker = AgentWorker(plugin_id="my_plugin", redis=redis, morpheus=rag2f.morpheus, rag2f=rag2f)
msg = await queue.dequeue("my_plugin", timeout=1)
await worker._handle_message(msg)  # single hook execution

status = await store.get_status_view(job.job_id)
print(status.to_dict())
```

### Notebook-friendly hooks
```python
from rag2f import RAG2F
from rag2f.core.morpheus.decorators import hook

@hook("rag2f_bootstrap_embedders", priority=5)
def my_embedder_hook(registry, rag2f):
    registry["my_embedder"] = MyEmbedder()
    return registry

rag2f = await RAG2F.create(hooks=[my_embedder_hook])
```

## Dev notes
- Requirements install per plugin: `Plugin.install_requirements(plugin_id, path)` (supports `pyproject.toml` or `requirements.txt`).
- Settings: Spock reads JSON/env; plugin settings schema via `settings_model`/`settings_schema`.
- Tests use fakeredis for async agents and mock plugins under `tests/mocks/plugins`.
