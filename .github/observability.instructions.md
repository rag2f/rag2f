---
name: RAG2F Observability Instructions
description: Agent-oriented observability rules for Python code in RAG2F. Use when adding or editing logs, hook execution paths, plugin lifecycle code, Spock config handling, FluxCapacitor tasks, or failure diagnostics.
applyTo: "src/**/*.py"
---

# RAG2F - Observability Rules

- Treat observability as part of the behavior contract, especially at hook boundaries, plugin activation, config loading, task execution, and failure paths.
- Use the helper in `rag2f.core.observability` instead of ad-hoc log strings: `observation_scope`, `debug_event`, `info_event`, `warning_event`, `error_event`, `exception_event`.
- Prefer structured key/value events with stable fields such as `plugin_id`, `hook_name`, `track_id`, `task_id`, `root_id`, `correlation_id`, `status`, and `error_type`.
- Use `debug` for detailed flow and bulky diagnostics. Use `info` only for important lifecycle milestones. Use `warning` for recoverable anomalies. Use `error` or `exception` for real failures; use `exception_event` when a stack trace is needed.
- Never log secrets, tokens, passwords, API keys, raw ENV values, or full sensitive payloads. Use the observability helper so fields are redacted consistently.
- If a debug log needs expensive serialization or counting, guard it with `logger.isEnabledFor(logging.DEBUG)` before doing the work.
- When adding a new execution entry point, bind context early with `observation_scope(...)` so downstream logs inherit the same `correlation_id`.