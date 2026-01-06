from rag2f.core.morpheus.decorators import hook

EXECUTION_LOG = []


@hook("agent_entry_hook")
def agent_entry_hook(payload_ref=None, context=None, metadata=None, rag2f=None):
    """Entry hook used by AgentWorker tests."""
    EXECUTION_LOG.append(
        {
            "name": "agent_entry_hook",
            "payload_ref": payload_ref,
            "metadata": metadata,
        }
    )
    if context:
        context.emit_child(
            "agent_child_hook",
            payload_ref={"repository": "crystal_chamber", "id": "child-doc"},
            metadata={"child": True},
        )
    if rag2f:
        rag2f.spock.set_rag2f_config("agent_entry_called", True)
    return {"ok": True}


@hook("agent_child_hook")
def agent_child_hook(payload_ref=None, metadata=None):
    EXECUTION_LOG.append(
        {
            "name": "agent_child_hook",
            "payload_ref": payload_ref,
            "metadata": metadata,
        }
    )
    return {"child": True}
