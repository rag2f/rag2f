"""Additional mock hook used to test hook priorities."""

from rag2f.core.morpheus.decorators import hook


@hook(priority=3)
def morpheus_test_hook_message(message, rag2f):
    """Append a priority marker for tests."""
    if "Priorities" in message:
        message += " priority 3"
    return message
