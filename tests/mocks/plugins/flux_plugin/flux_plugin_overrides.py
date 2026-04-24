"""Plugin activation hooks for FluxCapacitor tests."""

from contextlib import suppress

from rag2f.core.flux_capacitor import InMemoryTaskQueue, InMemoryTaskStore
from rag2f.core.morpheus.decorators.plugin_decorator import plugin
from rag2f.core.rag2f import RAG2F


@plugin
def activated(plugin, rag2f_instance: RAG2F):
    """Register in-memory task store and queue for tests."""
    manager = rag2f_instance.task_manager
    if manager is None:
        return
    with suppress(ValueError):
        manager.register_store("memory", InMemoryTaskStore())
    with suppress(ValueError):
        manager.register_queue("memory", InMemoryTaskQueue())
    manager.set_default_store("memory")
    manager.set_default_queue("memory")


@plugin
def deactivated(plugin, rag2f_instance: RAG2F):
    """Cleanup task store and queue registrations."""
    manager = rag2f_instance.task_manager
    if manager is None:
        return
    manager.unregister_store("memory")
    manager.unregister_queue("memory")
