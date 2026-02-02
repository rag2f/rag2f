"""Minimal FluxCapacitor task execution tests."""

from __future__ import annotations

import importlib

from rag2f.core.flux_capacitor import InMemoryTaskQueue, InMemoryTaskStore


def test_flux_capacitor_runs_task_tree(rag2f) -> None:
    flux = rag2f.task_manager

    store = InMemoryTaskStore()
    queue = InMemoryTaskQueue()
    flux.register_store("test_memory", store)
    flux.register_queue("test_memory", queue)
    flux.set_default_store("test_memory")
    flux.set_default_queue("test_memory")

    hooks_module = importlib.import_module("plugins.flux_plugin.flux_hooks")
    hooks_module.EXECUTION_LOG.clear()

    root_id = flux.enqueue(
        plugin_id="flux_plugin",
        hook="flux_entry_hook",
        payload_ref={"repository": "repo", "id": "payload-1"},
    )

    while flux.run_once():
        pass

    parent = store.get_task(root_id)
    assert parent is not None
    assert parent.finished_at is not None
    assert parent.error is None

    children = store.list_children(root_id)
    assert len(children) == 1
    child = children[0]
    assert child.parent_id == root_id
    assert child.finished_at is not None
    assert child.error is None

    assert hooks_module.EXECUTION_LOG == ["flux_entry_hook", "flux_child_hook"]
