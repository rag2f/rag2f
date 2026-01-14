"""Mock hooks used by the test plugin."""

from rag2f.core.morpheus.decorators import hook


@hook
def get_id_input_text(current_id, text, rag2f):
    """Return a deterministic id derived from the input text when none is provided."""
    if current_id:
        return current_id
    base_text = (text or "").strip() or "input"
    return f"{base_text}-mock-id"


@hook
def check_duplicated_input_text(duplicated, item_id, text, rag2f):
    """Mark inputs containing the word 'duplicate' as duplicates."""
    normalized = (text or "").lower()
    if "duplicate" in normalized:
        return True
    return duplicated


@hook
def handle_text_foreground(done, item_id, text, rag2f):
    """Signal that any text containing 'handled' has already been processed."""
    if done:
        return done
    normalized = (text or "").lower()
    return "handled" in normalized
