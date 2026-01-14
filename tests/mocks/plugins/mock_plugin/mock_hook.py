"""Mock hook used to test Morpheus hook ordering."""

from rag2f.core.morpheus.decorators import hook


@hook(priority=2)
def morpheus_test_hook_message(message, rag2f):
    """Append a priority marker for tests."""
    if "Priorities" in message:
        message += " priority 2"
    return message
