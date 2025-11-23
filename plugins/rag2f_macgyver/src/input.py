from rag2f.core.morpheus.decorators import hook


@hook(priority=2)
def handle_text_foreground(message,rag2f):
    # Mock implementation: mark as duplicated if message already exists in rag2f storage
    if rag2f and message in rag2f.storage.get_all_messages():
        return True
    return False