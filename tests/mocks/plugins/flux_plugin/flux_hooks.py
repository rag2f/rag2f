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


@hook("flux_fanout_root_hook")
def flux_fanout_root_hook(context=None, **kwargs):
    EXECUTION_LOG.append("flux_fanout_root_hook")
    if context is not None:
        context.emit_child(
            "flux_branch_hook",
            payload_ref={"repository": "repo", "id": "branch-1", "meta": {"kind": "branch"}},
        )
        context.emit_child(
            "flux_leaf_hook",
            payload_ref={"repository": "repo", "id": "leaf-1", "meta": {"kind": "leaf"}},
        )
    return {"ok": True}


@hook("flux_branch_hook")
def flux_branch_hook(context=None, **kwargs):
    EXECUTION_LOG.append("flux_branch_hook")
    if context is not None:
        context.emit_child(
            "flux_grandchild_a_hook",
            payload_ref={"repository": "repo", "id": "grandchild-a", "meta": {"kind": "leaf"}},
        )
        context.emit_child(
            "flux_grandchild_b_hook",
            payload_ref={"repository": "repo", "id": "grandchild-b", "meta": {"kind": "leaf"}},
        )
    return {"branch": True}


@hook("flux_leaf_hook")
def flux_leaf_hook(**kwargs):
    EXECUTION_LOG.append("flux_leaf_hook")
    return {"leaf": True}


@hook("flux_grandchild_a_hook")
def flux_grandchild_a_hook(**kwargs):
    EXECUTION_LOG.append("flux_grandchild_a_hook")
    return {"grandchild": "a"}


@hook("flux_grandchild_b_hook")
def flux_grandchild_b_hook(**kwargs):
    EXECUTION_LOG.append("flux_grandchild_b_hook")
    return {"grandchild": "b"}
