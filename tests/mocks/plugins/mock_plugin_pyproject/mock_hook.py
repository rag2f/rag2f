"""Mock hook for the pyproject-based mock plugin."""

from rag2f.core.morpheus.decorators import hook


@hook(priority=4)
def morpheus_test_hook_message(message, rag2f):
    """Append a priority marker for tests."""
    if "Priorities" in message:
        message += " priority 4"
    return message
