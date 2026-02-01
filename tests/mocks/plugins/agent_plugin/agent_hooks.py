"""Hooks used by async agent tests."""

from rag2f.core.morpheus.decorators import hook

EXECUTION_LOG: list[str] = []


@hook("agent_entry_hook")
def agent_entry_hook(context=None, rag2f=None, **kwargs):
    EXECUTION_LOG.append("agent_entry_hook")
    if context is not None:
        context.emit_child(
            "agent_child_hook",
            payload_ref={"repository": "repo", "id": "payload-1"},
            metadata={"note": "spawned"},
        )
    if rag2f is not None:
        rag2f.spock.set_plugin_config("agent_plugin", "entry_hook_ran", True)
    return {"ok": True}


@hook("agent_child_hook")
def agent_child_hook(**kwargs):
    EXECUTION_LOG.append("agent_child_hook")
    return {"child": True}
