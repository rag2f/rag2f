from rag2f.core.morpheus.decorators import hook


@hook(priority=2)
def morpheus_test_hook_message(message,rag2f):
    if "Priorities" in message:
        message += " priority 2"
    return message
