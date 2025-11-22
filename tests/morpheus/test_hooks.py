import pytest

from rag2f.core.morpheus.decorators.hook import PillHook


def test_hook_priority_execution(morpheus):
    message="Priorities:"
    out = morpheus.execute_hook("morpheus_test_hook_message", message, rag2f=None)
    assert out == "Priorities: priority 3 priority 2"

