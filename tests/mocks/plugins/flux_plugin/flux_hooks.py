"""Hooks used by FluxCapacitor tests."""

from rag2f.core.morpheus.decorators import hook

EXECUTION_LOG: list[str] = []


@hook("flux_entry_hook")
def flux_entry_hook(context=None, **kwargs):
    EXECUTION_LOG.append("flux_entry_hook")
    if context is not None:
        context.emit_child(
            "flux_child_hook",
            payload_ref={"repository": "repo", "id": "payload-1"},
        )
    return {"ok": True}


@hook("flux_child_hook")
def flux_child_hook(**kwargs):
    EXECUTION_LOG.append("flux_child_hook")
    return {"child": True}
