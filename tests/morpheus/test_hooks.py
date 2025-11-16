import pytest

from rag2f.core.morpheus.decorators.hook import PillHook


@pytest.mark.asyncio
async def test_hook_discovery(morpheus):
    mock_plugin_hooks = morpheus.plugins["mock_plugin"].hooks
    assert len(mock_plugin_hooks) > 0
    plugin = morpheus.plugins["mock_plugin"]
    # Check that plugin._id is set and matches plugin.id
    assert hasattr(plugin, "_id")
    assert plugin._id == plugin.id
    for h in mock_plugin_hooks:
        assert isinstance(h, PillHook)
        # Check that hook.plugin_id is set and matches plugin._id
        assert hasattr(h, "plugin_id")
        assert h.plugin_id == plugin._id

def test_hook_priority_execution(morpheus):
    message="Priorities:"
    out = morpheus.execute_hook("morpheus_test_hook_message", message, rag2f=None)
    assert out == "Priorities: priority 3 priority 2"

