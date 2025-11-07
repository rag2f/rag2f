from rag2f.core.morpheus.decorators import hook


@hook(priority=3)
def before_cat_sends_message(message,rag2f):
    if "Priorities" in message:
        message += " priority 3"
    return message