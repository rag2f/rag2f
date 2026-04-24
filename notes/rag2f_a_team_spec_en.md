# Specifications — ATeam plugin-first for RAG2F

## Name and alias
The functionality is named **ATeam**.

### Recommended public name
- `a_team`

### Required alias
- `agent_manager`

### Compatibility rule
The primary functional and documentation name is **ATeam**.
At runtime, the manager must be exposed as `rag2f.a_team` and may also keep the alias `rag2f.agent_manager` for compatibility, readability, or transition purposes.

### Style note
In documentation and new code, prefer the name **ATeam** / `a_team`.
The alias `agent_manager` remains secondary and descriptive.

---

## Purpose
Define a **plugin-first** extension for RAG2F that allows plugins to:
- register one or more LLM agents through a registry system consistent with other framework managers;
- invoke a specific agent by key (`agent_key`) or use the plugin’s default;
- obtain, when needed, the **original object** of the registered agent/adapter, so as to use provider-specific or underlying framework APIs;
- build prompts **dynamically** via **webhooks / Morpheus hooks**;
- keep the core lightweight, with minimal DTO/dataclasses and without enforcing an external agent framework in the kernel.

---

## Design principles

### 1) Plugin-first, minimal core
The core introduces only:
- a new manager/registry for agents;
- a minimal execution protocol;
- lightweight DTOs;
- standard hooks for prompt resolution.

The core **must not** depend directly on external agent frameworks. Concrete adapters live in plugins.

### 2) Explicit registry, aligned with other managers
Agent registration happens in the plugin lifecycle `activated()`, just like repositories and embedders.

### 3) Both “uniform” and “casted” access
The manager must provide:
- a uniform API for executing an agent;
- the ability to retrieve the original concrete instance (`raw agent`) to use provider/framework-specific features.

### 4) Dynamic prompt via webhook
The prompt is not a static string in the core, but built via hooks. A plugin can:
- contribute prompt fragments;
- select prompts based on context;
- differentiate prompt versions/variants.

### 5) Lightweight dataclasses
Dataclasses must include only strictly necessary orchestration fields and must not replicate full provider runtime state.

### 6) Consistency with existing patterns
ATeam must be designed by explicitly following existing managers that use:
- `register(...)`
- `get(...)`
- `get_default(...)`
- centralized configuration via Spock
- plugin lifecycle registration

Goal: provide a consistent developer experience.

---

## Terminology
- **ATeam**: agent orchestration/registry functionality.
- **a_team**: recommended runtime alias.
- **agent_manager**: secondary/compatibility alias.
- **AgentAdapter**: minimal contract for uniform execution.
- **Raw agent**: original object registered by the plugin.
- **PromptContext**: context passed to hooks to build prompts.
- **PromptFragment**: prompt portion contributed by a plugin.
- **ResolvedPrompt**: final prompt ready for execution.

---

## Functional goals

### Agent registry
Each plugin can register multiple agents with unique keys:
- `my_plugin.default`
- `my_plugin.router`
- `my_plugin.synthesizer`

Each plugin can define its own default agent.

### Agent retrieval
The manager must allow:
- base typed retrieval as `AgentAdapter`;
- retrieval of the original object;
- retrieval of plugin default agent;
- existence checks and key listing.

### Agent execution
Expose `execute_*` methods:
- `execute_run(...)`
- `execute_run_async(...)`

Execution must rely only on the adapter contract.

### Prompt resolution
Prompt must be resolved before execution using hooks, with visibility on:
- caller identity;
- calling plugin/hook;
- purpose;
- parameters;
- prompt version.

### Compatibility
Registered objects may be adapters over any external framework.
The manager must not depend on their internals.

---

## Non-goals
- No mandatory dependency on external agent frameworks.
- No advanced provider-specific orchestration.
- No heavy or tightly coupled DTOs.
- No implicit full context injection into prompts.

---

## Architecture

### 1. ATeam manager
Responsibilities:
- registration;
- default resolution;
- lookup;
- raw access;
- execution;
- prompt hooks.

Excluded:
- provider handling;
- persistence;
- provider-specific logic.

Runtime aliases:
- `rag2f.a_team`
- `rag2f.agent_manager`

---

### 2. AgentAdapter contract
Minimal required capabilities:
- sync/async execution;
- expose `raw`;
- minimal metadata.

Example (illustrative):
```python
class AgentAdapter(Protocol):
    def run(self, request, *, rag2f): ...
    async def run_async(self, request, *, rag2f): ...
    @property
    def raw(self): ...
```

---

### 3. Registry entry and casted access
Each entry stores:
- key;
- plugin owner;
- adapter;
- raw object;
- metadata.

Access modes:
- uniform: `get()`, `execute_run()`;
- advanced: `get_raw()`.

---

### 4. Prompt via hooks
Hooks:
- `agent_collect_prompt_fragments`
- `agent_finalize_prompt`
- optional lifecycle hooks

Manager orchestrates only; plugins define prompt content.

---

## Alignment with existing managers
Follow patterns:
- `register(...)`
- `get(...)`, `has(...)`
- `get_default(...)`
- Spock-based configuration
- plugin lifecycle registration

Goal: zero surprise for developers.

---

## DTOs

### AgentRunRequest
Minimal invocation structure.

### PromptContext
Single object for hook decisions.

### PromptFragment
Scoped prompt contribution.

### ResolvedPrompt
Final prompt passed to adapter.

### AgentRunResult
Framework-consistent result object.

---

## Manager API
- `register(...)`
- `get(...)`
- `get_raw(...)`
- `get_default(...)`
- `list_keys(...)`
- `has(...)`
- `unregister(...)`
- `execute_run(...)`
- `execute_run_async(...)`

---

## Default resolution
Priority:
1. explicit agent_key;
2. plugin default;
3. global default;
4. error.

Configured via **Spock**.

Config priority:
ENV/runtime > JSON > plugin default > fallback.

---

## Spock integration
Suggested keys:
- `plugins.<plugin_id>.default_agent`
- `plugins.<plugin_id>.agents.<agent_key>.*`
- `rag2f.a_team_default`

---

## Plugin lifecycle
Register in `activated()`.

---

## Prompt hooks
- collect fragments
- finalize prompt

---

## Raw access
- adapter exposes `raw`
- manager exposes `get_raw()`

---

## Error handling
Use Result pattern.

---

## Logging
Track:
- agent key
- plugin
- purpose
- caller hook

---

## Testing
Cover:
- registry
- defaults (including Spock)
- prompt hooks
- raw access

---

## Constraints
- keep lightweight
- no external dependency
- reuse patterns

---

## Roadmap
1. core
2. hooks
3. config
4. extensions

---

## Acceptance criteria
- multi-agent support
- per-plugin default
- raw access
- hook-driven prompt
- lightweight DTOs
- consistent API
- Spock integration

---

## Final note
Keep:
- core orchestration in core
- adapters in plugins
- prompt logic in hooks

Avoid strong coupling to a single SDK.
