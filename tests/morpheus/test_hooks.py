import pytest

from rag2f.core.morpheus.decorators.hook import PillHook


@pytest.mark.asyncio
async def test_hook_discovery(morpheus):
    mock_plugin_hooks = morpheus.plugins["mock_plugin"].hooks
    assert len(mock_plugin_hooks) > 0
    for h in mock_plugin_hooks:
        assert isinstance(h, PillHook)
        assert h.plugin_id == "mock_plugin"

def test_hook_priority_execution(morpheus):
    message="Priorities:"
    out = morpheus.execute_hook("before_cat_sends_message", message, rag2f=None)
    assert out == "Priorities: priority 3 priority 2"
