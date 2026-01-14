"""Tests for Morpheus hook execution ordering."""


def test_hook_priority_execution(morpheus):
    """Hooks should execute in descending priority order."""
    message = "Priorities:"
    out = morpheus.execute_hook("morpheus_test_hook_message", message, rag2f=None)
    assert out == "Priorities: priority 4 priority 3 priority 2"
